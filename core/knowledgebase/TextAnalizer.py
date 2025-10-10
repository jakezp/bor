from __future__ import annotations

from pathlib import Path
import os

from langchain_core.prompts import PromptTemplate
from langchain_aws import ChatBedrock
from langchain_core.messages import (
    HumanMessage,
    SystemMessage
)

from core.knowledgebase import constants
from core.knowledgebase.AWSAuth import AWSAuthenticator


class TextAnalizer:
    def __init__(self) -> None:

        # Get AWS Bedrock client
        authenticator = AWSAuthenticator()
        bedrock_runtime = authenticator.get_bedrock_runtime_client()
        
        self.model = ChatBedrock(
            model=constants.BEDROCK_MODEL_ID,
            client=bedrock_runtime,
            model_kwargs={
                "temperature": constants.LLM_MODEL_TEMPERATURE,
                "max_tokens": 4096
            }
        )

        self.prompt_names = [
            'prompt_generate', 'system_message_generate',
            'prompt_update', 'system_message_update',
            'prompt_question', 'system_message_question',
            'prompt_explain', 'system_message_explain',
            'prompt_optimize', 'system_message_optimize',
            'prompt_debug', 'system_message_debug',
        ]
        self.prompts = {}
        self.init_prompts()

        self.messages = []

        return

    def init_prompts(self) -> None:

        for prompt_name in self.prompt_names:
            prompt_path = Path(os.path.join(
                os.path.dirname(__file__), 'prompts', prompt_name))
            prompt_text = prompt_path.read_text()
            prompt_template = PromptTemplate.from_template(prompt_text)
            self.prompts[prompt_name] = prompt_template
        return

    def text_to_cypher_create(self, text: str, repo_path: str, file_path: str) -> str:
        self.messages = [
            SystemMessage(
                content=self.prompts['system_message_generate'].format()),
            HumanMessage(content=self.prompts['prompt_generate'].format(
                prompt=text, repo_path=repo_path, file_path=file_path))
        ]
        response = self.model.invoke(self.messages)
        return str(response.content) if response.content else ""

    def data_and_text_to_cypher_update(self, data: str, text: str, repo_path: str, file_path: str) -> str:
        self.messages = [
            SystemMessage(
                content=self.prompts['system_message_update'].format()),
            HumanMessage(content=self.prompts['prompt_update'].format(
                data=data, prompt=text, repo_path=repo_path, file_path=file_path))
        ]
        response = self.model.invoke(self.messages)
        return str(response.content) if response.content else ""

    def generate_questions(self, text: str) -> str:
        self.messages = [
            SystemMessage(
                content=self.prompts['system_message_question'].format()),
            HumanMessage(
                content=self.prompts['prompt_question'].format(prompt=text))
        ]
        response = self.model.invoke(self.messages)
        return str(response.content) if response.content else ""
    
    def _general_code_question(self, prompt_name: str, text: str) -> str:
        self.messages = [
            SystemMessage(
                content=self.prompts[f'system_message_{prompt_name}'].format()),
            HumanMessage(
                content=self.prompts[f'prompt_{prompt_name}'].format(code=text))
        ]
        response = self.model.invoke(self.messages)
        return str(response.content) if response.content else ""
    
    def optimize_code_style(self, text: str) -> str:
        return self._general_code_question('optimize', text)

    def explain_code(self, text: str) -> str:
        return self._general_code_question('explain', text)

    def debug_code(self, text: str) -> str:
        return self._general_code_question('debug', text)


if __name__ == '__main__':

    ta = TextAnalizer()

    example_reponame = 'History'
    example_repopath = os.path.join(os.path.dirname(
        __file__), 'examples', example_reponame)

    example_fname = 'napoleon.txt'
    example_fpath = os.path.join(example_repopath, example_fname)

    example_text = Path(example_fpath).read_text()

    ret = ta.text_to_cypher_create(
        example_text, example_repopath, example_fname)
    print(ret)

    questionable_text = """Napoleon initiated many liberal reforms that have persisted, 
    and is considered one of the greatest ever military commanders. His campaigns are still studied at military academies worldwide."""
    ret = ta.generate_questions(questionable_text)
    print(ret)

    code = """
        def evens(l):
            return [x for x in l if x % 2 == 0]
    """

    ret = ta.explain_code(code)
    print(ret)
