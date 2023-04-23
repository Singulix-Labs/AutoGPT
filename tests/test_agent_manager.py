import unittest
from typing import List

from autogpt.agent.agent_manager import AgentManager
from tests.utils import requires_api_key


class TestAgentManager(unittest.TestCase):
    def setUp(self):
        self.agent_manager = AgentManager()
        self.task = "translate English to French"
        self.prompt = (
            "Translate the following English text to French: 'Hello, how are you?'"
        )
        self.model = "gpt-4"

    @requires_api_key("OPENAI_API_KEY")
    def test_create_agent(self):
        key, agent_reply = self.agent_manager.create_agent(
            self.task, self.prompt, self.model
        )
        self.assertIsInstance(key, int)
        self.assertIsInstance(agent_reply, str)
        self.assertIn(key, self.agent_manager.agents)

    @requires_api_key("OPENAI_API_KEY")
    def test_message_agent(self):
        key, _ = self.agent_manager.create_agent(self.task, self.prompt, self.model)
        user_message = "Please translate 'Good morning' to French."
        agent_reply = self.agent_manager.message_agent(key, user_message)
        self.assertIsInstance(agent_reply, str)

    @requires_api_key("OPENAI_API_KEY")
    def test_list_agents(self):
        key, _ = self.agent_manager.create_agent(self.task, self.prompt, self.model)
        agents_list = self.agent_manager.list_agents()
        self.assertIsInstance(agents_list, list)
        self.assertIn((key, self.task), agents_list)

    @requires_api_key("OPENAI_API_KEY")
    def test_delete_agent(self):
        key, _ = self.agent_manager.create_agent(self.task, self.prompt, self.model)
        success = self.agent_manager.delete_agent(key)
        self.assertTrue(success)
        self.assertNotIn(key, self.agent_manager.agents)


if __name__ == "__main__":
    unittest.main()
