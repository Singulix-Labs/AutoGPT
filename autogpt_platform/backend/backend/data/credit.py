from abc import ABC, abstractmethod
from datetime import datetime, timezone

import stripe
from prisma import Json
from prisma.enums import CreditTransactionType
from prisma.errors import UniqueViolationError
from prisma.models import CreditTransaction, User
from prisma.types import CreditTransactionCreateInput, CreditTransactionWhereInput

from backend.data import db
from backend.data.block import Block, BlockInput, get_block
from backend.data.block_cost_config import BLOCK_COSTS
from backend.data.cost import BlockCost, BlockCostType
from backend.data.user import get_user_by_id
from backend.util.settings import Settings

settings = Settings()
stripe.api_key = settings.secrets.stripe_api_key


class UserCreditBase(ABC):
    @abstractmethod
    async def get_credits(self, user_id: str) -> int:
        """
        Get the current credits for the user.

        Returns:
            int: The current credits for the user.
        """
        pass

    @abstractmethod
    async def spend_credits(
        self,
        user_id: str,
        block_id: str,
        input_data: BlockInput,
        data_size: float,
        run_time: float,
    ) -> int:
        """
        Spend the credits for the user based on the block usage.

        Args:
            user_id (str): The user ID.
            block_id (str): The block ID.
            input_data (BlockInput): The input data for the block.
            data_size (float): The size of the data being processed.
            run_time (float): The time taken to run the block.

        Returns:
            int: amount of credit spent
        """
        pass

    @abstractmethod
    async def top_up_credits(self, user_id: str, amount: int):
        """
        Top up the credits for the user immediately.

        Args:
            user_id (str): The user ID.
            amount (int): The amount to top up.
        """
        pass

    @abstractmethod
    async def top_up_intent(self, user_id: str, amount: int) -> str:
        """
        Create a payment intent to top up the credits for the user.

        Args:
            user_id (str): The user ID.
            amount (int): The amount of credits to top up.

        Returns:
            str: The redirect url to the payment page.
        """
        pass

    @abstractmethod
    async def fulfill_checkout(
        self, *, session_id: str | None = None, user_id: str | None = None
    ):
        """
        Fulfill the Stripe checkout session.

        Args:
            session_id (str | None): The checkout session ID. Will try to fulfill most recent if None.
            user_id (str | None): The user ID must be provided if session_id is None.
        """
        pass

    @staticmethod
    def time_now() -> datetime:
        return datetime.now(timezone.utc)

    # ====== Transaction Helper Methods ====== #
    # Any modifications to the transaction table should only be done through these methods #

    async def _get_credits(self, user_id: str) -> tuple[int, datetime]:
        """
        Returns the current balance of the user & the latest balance snapshot time.
        """
        top_time = self.time_now()
        snapshot = await CreditTransaction.prisma().find_first(
            where={
                "userId": user_id,
                "createdAt": {"lte": top_time},
                "isActive": True,
                "runningBalance": {"not": None},  # type: ignore
            },
            order={"createdAt": "desc"},
        )
        if snapshot:
            return snapshot.runningBalance or 0, snapshot.createdAt

        # No snapshot: Manually calculate balance using current month's transactions.
        low_time = top_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        transactions = await CreditTransaction.prisma().group_by(
            by=["userId"],
            sum={"amount": True},
            where={
                "userId": user_id,
                "createdAt": {"gte": low_time, "lte": top_time},
                "isActive": True,
            },
        )
        transaction_balance = (
            transactions[0].get("_sum", {}).get("amount", 0) if transactions else 0
        )
        return transaction_balance, datetime.min

    async def _enable_transaction(
        self, transaction_key: str, user_id: str, metadata: Json
    ):

        transaction = await CreditTransaction.prisma().find_first_or_raise(
            where={"transactionKey": transaction_key, "userId": user_id}
        )

        if transaction.isActive:
            return

        async with db.locked_transaction(f"usr_trx_{user_id}"):
            user_balance, _ = await self._get_credits(user_id)

            await CreditTransaction.prisma().update(
                where={
                    "creditTransactionIdentifier": {
                        "transactionKey": transaction_key,
                        "userId": user_id,
                    }
                },
                data={
                    "isActive": True,
                    "runningBalance": user_balance + transaction.amount,
                    "createdAt": self.time_now(),
                    "metadata": metadata,
                },
            )

    async def _add_transaction(
        self,
        user_id: str,
        amount: int,
        transaction_type: CreditTransactionType,
        is_active: bool = True,
        transaction_key: str | None = None,
        block_id: str | None = None,
        metadata: Json = Json({}),
    ):
        async with db.locked_transaction(f"usr_trx_{user_id}"):
            # Get latest balance snapshot
            user_balance, _ = await self._get_credits(user_id)
            if amount < 0 and user_balance < abs(amount):
                raise ValueError(
                    f"Insufficient balance for user {user_id}, balance: {user_balance}, amount: {amount}"
                )

            # Create the transaction
            transaction_data: CreditTransactionCreateInput = {
                "userId": user_id,
                "amount": amount,
                "runningBalance": user_balance + amount,
                "type": transaction_type,
                "blockId": block_id,
                "metadata": metadata,
                "isActive": is_active,
                "createdAt": self.time_now(),
            }
            if transaction_key:
                transaction_data["transactionKey"] = transaction_key
            await CreditTransaction.prisma().create(data=transaction_data)

            return user_balance + amount


class UserCredit(UserCreditBase):

    def _block_usage_cost(
        self,
        block: Block,
        input_data: BlockInput,
        data_size: float,
        run_time: float,
    ) -> tuple[int, BlockInput]:
        block_costs = BLOCK_COSTS.get(type(block))
        if not block_costs:
            return 0, {}

        for block_cost in block_costs:
            if not self._is_cost_filter_match(block_cost.cost_filter, input_data):
                continue

            if block_cost.cost_type == BlockCostType.RUN:
                return block_cost.cost_amount, block_cost.cost_filter

            if block_cost.cost_type == BlockCostType.SECOND:
                return (
                    int(run_time * block_cost.cost_amount),
                    block_cost.cost_filter,
                )

            if block_cost.cost_type == BlockCostType.BYTE:
                return (
                    int(data_size * block_cost.cost_amount),
                    block_cost.cost_filter,
                )

        return 0, {}

    def _is_cost_filter_match(
        self, cost_filter: BlockInput, input_data: BlockInput
    ) -> bool:
        """
        Filter rules:
          - If cost_filter is an object, then check if cost_filter is the subset of input_data
          - Otherwise, check if cost_filter is equal to input_data.
          - Undefined, null, and empty string are considered as equal.
        """
        if not isinstance(cost_filter, dict) or not isinstance(input_data, dict):
            return cost_filter == input_data

        return all(
            (not input_data.get(k) and not v)
            or (input_data.get(k) and self._is_cost_filter_match(v, input_data[k]))
            for k, v in cost_filter.items()
        )

    async def spend_credits(
        self,
        user_id: str,
        block_id: str,
        input_data: BlockInput,
        data_size: float,
        run_time: float,
    ) -> int:
        block = get_block(block_id)
        if not block:
            raise ValueError(f"Block not found: {block_id}")

        cost, matching_filter = self._block_usage_cost(
            block=block, input_data=input_data, data_size=data_size, run_time=run_time
        )
        if cost == 0:
            return 0

        await self._add_transaction(
            user_id=user_id,
            amount=-cost,
            transaction_type=CreditTransactionType.USAGE,
            block_id=block.id,
            metadata=Json(
                {
                    "block": block.name,
                    "input": matching_filter,
                }
            ),
        )

        return cost

    async def top_up_credits(self, user_id: str, amount: int):
        if amount < 0:
            raise ValueError(f"Top up amount must not be negative: {amount}")

        await self._add_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=CreditTransactionType.TOP_UP,
        )

    @staticmethod
    async def _get_stripe_customer_id(user_id: str) -> str:
        user = await get_user_by_id(user_id)
        if not user:
            raise ValueError(f"User not found: {user_id}")

        if user.stripeCustomerId:
            return user.stripeCustomerId

        customer = stripe.Customer.create(name=user.name or "", email=user.email)
        await User.prisma().update(
            where={"id": user_id}, data={"stripeCustomerId": customer.id}
        )
        return customer.id

    async def top_up_intent(self, user_id: str, amount: int) -> str:
        # Create checkout session
        # https://docs.stripe.com/checkout/quickstart?client=react
        # unit_amount param is always in the smallest currency unit (so cents for usd)
        # which is equal to amount of credits
        checkout_session = stripe.checkout.Session.create(
            customer=await self._get_stripe_customer_id(user_id),
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "AutoGPT Platform Credits",
                        },
                        "unit_amount": amount,
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=settings.config.platform_base_url
            + "/store/credits?topup=success",
            cancel_url=settings.config.platform_base_url
            + "/store/credits?topup=cancel",
        )

        # Create pending transaction
        await self._add_transaction(
            user_id=user_id,
            amount=amount,
            transaction_type=CreditTransactionType.TOP_UP,
            transaction_key=checkout_session.id,
            is_active=False,
            metadata=Json({"checkout_session": checkout_session}),
        )

        return checkout_session.url or ""

    # https://docs.stripe.com/checkout/fulfillment
    async def fulfill_checkout(
        self, *, session_id: str | None = None, user_id: str | None = None
    ):
        if (not session_id and not user_id) or (session_id and user_id):
            raise ValueError("Either session_id or user_id must be provided")

        # Retrieve CreditTransaction
        find_filter: CreditTransactionWhereInput = {
            "type": CreditTransactionType.TOP_UP,
            "isActive": False,
        }
        if session_id:
            find_filter["transactionKey"] = session_id
        if user_id:
            find_filter["userId"] = user_id

        # Find the most recent inactive top-up transaction
        credit_transaction = await CreditTransaction.prisma().find_first_or_raise(
            where=find_filter,
            order={"createdAt": "desc"},
        )

        # This can be called multiple times for one id, so ignore if already fulfilled
        if not credit_transaction:
            return

        # Retrieve the Checkout Session from the API
        checkout_session = stripe.checkout.Session.retrieve(
            credit_transaction.transactionKey
        )

        # Check the Checkout Session's payment_status property
        # to determine if fulfillment should be performed
        if checkout_session.payment_status in ["paid", "no_payment_required"]:
            await self._enable_transaction(
                transaction_key=credit_transaction.transactionKey,
                user_id=credit_transaction.userId,
                metadata=Json({"checkout_session": checkout_session}),
            )

    async def get_credits(self, user_id: str) -> int:
        balance, _ = await self._get_credits(user_id)
        return balance


class BetaUserCredit(UserCredit):
    """
    This is a temporary class to handle the test user utilizing monthly credit refill.
    TODO: Remove this class & its feature toggle.
    """

    def __init__(self, num_user_credits_refill: int):
        self.num_user_credits_refill = num_user_credits_refill

    async def get_credits(self, user_id: str) -> int:
        cur_time = self.time_now().date()
        balance, snapshot_time = await self._get_credits(user_id)
        if (snapshot_time.year, snapshot_time.month) == (cur_time.year, cur_time.month):
            return balance

        try:
            await CreditTransaction.prisma().create(
                data={
                    "transactionKey": f"MONTHLY-CREDIT-TOP-UP-{cur_time}",
                    "userId": user_id,
                    "amount": self.num_user_credits_refill,
                    "runningBalance": self.num_user_credits_refill,
                    "type": CreditTransactionType.TOP_UP,
                    "metadata": Json({}),
                    "isActive": True,
                    "createdAt": self.time_now(),
                }
            )
        except UniqueViolationError:
            pass  # Already refilled this month

        return self.num_user_credits_refill


class DisabledUserCredit(UserCreditBase):
    async def get_credits(self, *args, **kwargs) -> int:
        return 0

    async def spend_credits(self, *args, **kwargs) -> int:
        return 0

    async def top_up_credits(self, *args, **kwargs):
        pass

    async def top_up_intent(self, *args, **kwargs) -> str:
        return ""

    async def fulfill_checkout(self, *args, **kwargs):
        pass


def get_user_credit_model() -> UserCreditBase:
    if not settings.config.enable_credit:
        return DisabledUserCredit()

    if settings.config.enable_beta_monthly_credit:
        return BetaUserCredit(settings.config.num_user_credits_refill)

    return UserCredit()


def get_block_costs() -> dict[str, list[BlockCost]]:
    return {block().id: costs for block, costs in BLOCK_COSTS.items()}
