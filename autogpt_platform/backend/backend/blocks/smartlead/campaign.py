from backend.blocks.smartlead._api import SmartLeadClient
from backend.blocks.smartlead._auth import (
    TEST_CREDENTIALS,
    TEST_CREDENTIALS_INPUT,
    SmartLeadCredentials,
    SmartLeadCredentialsInput,
)
from backend.blocks.smartlead.models import (
    AddLeadsRequest,
    AddLeadsToCampaignResponse,
    CreateCampaignRequest,
    CreateCampaignResponse,
    LeadInput,
    LeadUploadSettings,
    SaveSequencesRequest,
    SaveSequencesResponse,
    Sequence,
)
from backend.data.block import Block, BlockCategory, BlockOutput, BlockSchema
from backend.data.model import SchemaField


class CreateCampaignBlock(Block):
    """Create a campaign in SmartLead"""

    class Input(BlockSchema):
        name: str = SchemaField(
            description="The name of the campaign",
        )
        credentials: SmartLeadCredentialsInput = SchemaField(
            description="SmartLead credentials",
        )

    class Output(BlockSchema):
        ok: bool = SchemaField(
            description="Whether the campaign was created successfully",
        )
        id: int = SchemaField(
            description="The ID of the created campaign",
        )
        name: str = SchemaField(
            description="The name of the created campaign",
        )
        created_at: str = SchemaField(
            description="The date and time the campaign was created",
        )
        error: str = SchemaField(
            description="Error message if the search failed",
            default="",
        )

    def __init__(self):
        super().__init__(
            id="8865699f-9188-43c4-89b0-79c84cfaa03e",
            description="Create a campaign in SmartLead",
            categories={BlockCategory.CRM},
            input_schema=CreateCampaignBlock.Input,
            output_schema=CreateCampaignBlock.Output,
            test_credentials=TEST_CREDENTIALS,
            test_input={"name": "Test Campaign", "credentials": TEST_CREDENTIALS_INPUT},
            test_output=[
                (
                    "campaign",
                    {
                        "id": "1",
                        "name": "Test Campaign",
                        "ok": True,
                        "created_at": "2024-01-01T00:00:00Z",
                    },
                )
            ],
            test_mock={
                "create_campaign": lambda name: CreateCampaignResponse(
                    ok=True,
                    id=1,
                    name=name,
                    created_at="2024-01-01T00:00:00Z",
                )
            },
        )

    def run(
        self,
        input_data: Input,
        *,
        credentials: SmartLeadCredentials,
        **kwargs,
    ) -> BlockOutput:
        client = SmartLeadClient(credentials.api_key.get_secret_value())

        # query = SearchPeopleRequest(**input_data.model_dump(exclude={"credentials"}))
        response = client.create_campaign(CreateCampaignRequest(name=input_data.name))

        yield "ok", response.ok
        yield "id", response.id
        yield "name", response.name
        yield "created_at", response.created_at


class AddLeadToCampaignBlock(Block):
    """Add a lead to a campaign in SmartLead"""

    class Input(BlockSchema):
        campaign_id: int = SchemaField(
            description="The ID of the campaign to add the lead to",
        )
        lead_list: list[LeadInput] = SchemaField(
            description="An array of JSON objects, each representing a lead's details. Can hold max 100 leads.",
            max_length=100,
            default=[],
            advanced=False,
        )
        settings: LeadUploadSettings = SchemaField(
            description="Settings for lead upload",
            default=LeadUploadSettings(),
        )
        credentials: SmartLeadCredentialsInput = SchemaField(
            description="SmartLead credentials",
        )

    class Output(BlockSchema):
        campaign_id: int = SchemaField(
            description="The ID of the campaign the lead was added to (passed through)",
        )
        ok: bool = SchemaField(
            description="Whether the lead was added to the campaign successfully",
        )
        upload_count: int = SchemaField(
            description="The number of leads added to the campaign",
        )
        already_added_to_campaign: int = SchemaField(
            description="The number of leads that were already added to the campaign",
        )
        duplicate_count: int = SchemaField(
            description="The number of emails that were duplicates",
        )
        invalid_email_count: int = SchemaField(
            description="The number of emails that were invalidly formatted",
        )
        is_lead_limit_exhausted: bool = SchemaField(
            description="Whether the lead limit was exhausted",
        )
        lead_import_stopped_count: int = SchemaField(
            description="The number of leads that were not added to the campaign because the lead import was stopped",
        )
        error: str = SchemaField(
            description="Error message if the lead was not added to the campaign",
            default="",
        )

    def __init__(self):
        super().__init__(
            id="fb8106a4-1a8f-42f9-a502-f6d07e6fe0ec",
            description="Add a lead to a campaign in SmartLead",
            categories={BlockCategory.CRM},
            input_schema=AddLeadToCampaignBlock.Input,
            output_schema=AddLeadToCampaignBlock.Output,
            test_credentials=TEST_CREDENTIALS,
            test_input={
                "campaign_id": 1,
                "lead_list": [],
                "credentials": TEST_CREDENTIALS_INPUT,
            },
            test_output=[
                (
                    "campaign",
                    {
                        "ok": True,
                        "upload_count": 1,
                    },
                )
            ],
            test_mock={
                "add_leads_to_campaign": lambda campaign_id, lead_list: AddLeadsToCampaignResponse(
                    ok=True,
                    upload_count=1,
                    already_added_to_campaign=0,
                    duplicate_count=0,
                    invalid_email_count=0,
                    is_lead_limit_exhausted=False,
                    lead_import_stopped_count=0,
                    error="",
                    total_leads=1,
                    block_count=0,
                    invalid_emails=[],
                    unsubscribed_leads=[],
                    bounce_count=0,
                )
            },
        )

    def run(
        self,
        input_data: Input,
        *,
        credentials: SmartLeadCredentials,
        **kwargs,
    ) -> BlockOutput:
        client = SmartLeadClient(credentials.api_key.get_secret_value())

        response = client.add_leads_to_campaign(
            AddLeadsRequest(
                campaign_id=input_data.campaign_id,
                lead_list=input_data.lead_list,
                settings=LeadUploadSettings(
                    ignore_global_block_list=False,
                    ignore_unsubscribe_list=False,
                    ignore_community_bounce_list=False,
                    ignore_duplicate_leads_in_other_campaign=False,
                ),
            )
        )

        yield "campaign_id", input_data.campaign_id
        yield "ok", response.ok
        yield "upload_count", response.upload_count
        if response.already_added_to_campaign:
            yield "already_added_to_campaign", response.already_added_to_campaign
        if response.duplicate_count:
            yield "duplicate_count", response.duplicate_count
        if response.invalid_email_count:
            yield "invalid_email_count", response.invalid_email_count
        if response.is_lead_limit_exhausted:
            yield "is_lead_limit_exhausted", response.is_lead_limit_exhausted
        if response.lead_import_stopped_count:
            yield "lead_import_stopped_count", response.lead_import_stopped_count
        if response.error:
            yield "error", response.error


class SaveCampaignSequencesBlock(Block):
    """Save sequences within a campaign"""

    class Input(BlockSchema):
        campaign_id: int = SchemaField(
            description="The ID of the campaign to save sequences for",
        )
        sequences: list[Sequence] = SchemaField(
            description="The sequences to save",
            default=[],
            advanced=False,
        )
        credentials: SmartLeadCredentialsInput = SchemaField(
            description="SmartLead credentials",
        )

    class Output(BlockSchema):
        ok: bool = SchemaField(
            description="Whether the sequences were saved successfully",
        )
        data: dict | str | None = SchemaField(
            description="Data from the API",
            default=None,
        )
        message: str = SchemaField(
            description="Message from the API",
            default="",
        )
        error: str = SchemaField(
            description="Error message if the sequences were not saved",
            default="",
        )

    def __init__(self):
        super().__init__(
            id="e7d9f41c-dc10-4f39-98ba-a432abd128c0",
            description="Save sequences within a campaign",
            categories={BlockCategory.CRM},
            input_schema=SaveCampaignSequencesBlock.Input,
            output_schema=SaveCampaignSequencesBlock.Output,
            test_credentials=TEST_CREDENTIALS,
            test_input={
                "campaign_id": 1,
                "sequences": [],
                "credentials": TEST_CREDENTIALS_INPUT,
            },
            test_output=[
                (
                    "campaign",
                    {
                        "ok": True,
                        "message": "Sequences saved successfully",
                    },
                )
            ],
            test_mock={
                "save_campaign_sequences": lambda campaign_id, sequences: SaveSequencesResponse(
                    ok=True,
                    message="Sequences saved successfully",
                )
            },
        )

    def run(
        self,
        input_data: Input,
        *,
        credentials: SmartLeadCredentials,
        **kwargs,
    ) -> BlockOutput:
        client = SmartLeadClient(credentials.api_key.get_secret_value())

        response = client.save_campaign_sequences(
            campaign_id=input_data.campaign_id,
            request=SaveSequencesRequest(sequences=input_data.sequences),
        )

        yield "ok", response.ok
        if response.data:
            yield "data", response.data
        if response.message:
            yield "message", response.message
        if response.error:
            yield "error", response.error
