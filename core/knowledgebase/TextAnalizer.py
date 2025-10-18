from __future__ import annotations

import os
import json
from datetime import datetime
from typing import List, Dict, Any

from core.knowledgebase import constants
from core.knowledgebase.AWSAuth import AWSAuthenticator
from core.knowledgebase.BedrockResponseParser import BedrockResponseParser


class TextAnalizer:
    def __init__(self) -> None:
        authenticator = AWSAuthenticator()
        self.bedrock_runtime = authenticator.get_bedrock_runtime_client()
        
        self.data_dir = os.environ.get("CHROMA_DATA_DIR", "/etc/chroma")
        os.makedirs(self.data_dir, exist_ok=True)

        self.prompts = {}
        self._init_prompts()

    def _init_prompts(self) -> None:
        prompt_files = [f for f in os.listdir(constants.PROMPTS_DIR) if not f.startswith('.')] 
        for file_name in prompt_files:
            prompt_path = os.path.join(constants.PROMPTS_DIR, file_name)
            with open(prompt_path, 'r') as f:
                self.prompts[file_name] = f.read()

    def _log_bedrock_io(self, file_path: str, prompt: list, raw_response: dict, parsed_response: str) -> None:
        """Logs the input, raw output, and parsed output of a Bedrock API call."""
        separator = f"--- LOG FOR {file_path} AT {datetime.now().isoformat()} ---\n"
        try:
            with open(os.path.join(self.data_dir, "tmp_input.txt"), "a", encoding="utf-8") as f:
                f.write(separator)
                f.write("\n".join([msg.content for msg in prompt]) + "\n\n")
            with open(os.path.join(self.data_dir, "tmp_output.txt"), "a", encoding="utf-8") as f:
                f.write(separator)
                try:
                    f.write(json.dumps(raw_response, indent=4, default=str) + "\n\n")
                except Exception:
                    # Fallback for non-serializable responses
                    f.write(str(raw_response) + "\n\n")
            with open(os.path.join(self.data_dir, "tmp_parsed.txt"), "a", encoding="utf-8") as f:
                f.write(separator)
                f.write(parsed_response + "\n\n")
        except Exception as e:
            print(f"Error writing to log files: {e}")

    def _invoke_model_with_logging(self, file_path: str, system_prompt: str, user_prompt: str) -> str:
        """Invokes Bedrock using the Messages/Converse API and logs I/O."""
        messages = [
            {"role": "user", "content": [{"text": user_prompt}]}
        ]
        system = {"text": system_prompt} if system_prompt else None

        request: Dict[str, Any] = {
            "modelId": constants.BEDROCK_MODEL_ID,
            "messages": messages,
            "inferenceConfig": {
                "temperature": constants.LLM_MODEL_TEMPERATURE,
                "maxTokens": constants.LLM_MAX_TOKENS,
            }
        }
        if system is not None:
            request["system"] = [system]

        raw = self.bedrock_runtime.converse(**request)
        # Extract plain text from Bedrock Converse response
        try:
            content_blocks = raw["output"]["message"]["content"]
            text_parts = [b.get("text", "") for b in content_blocks if isinstance(b, dict)]
            raw_text = "\n".join([t for t in text_parts if t])
        except Exception:
            raw_text = json.dumps(raw, default=str)

        parsed_response = BedrockResponseParser.parse_cypher_from_message(raw_text)
        
        self._log_bedrock_io(
            file_path=file_path,
            prompt=[type("Msg", (), {"content": system_prompt}), type("Msg", (), {"content": user_prompt})],
            raw_response=raw,
            parsed_response=parsed_response
        )
        
        return parsed_response

    def text_to_cypher_create(self, text: str, repo_path: str, file_path: str) -> str:
        system = self.prompts['system_message_generate']
        user = self.prompts['prompt_generate'].format(
            prompt=text, repo_path=repo_path, file_path=file_path)
        return self._invoke_model_with_logging(file_path, system, user)

    def data_and_text_to_cypher_update(self, data: str, text: str, repo_path: str, file_path: str) -> str:
        system = self.prompts['system_message_update']
        user = self.prompts['prompt_update'].format(
            data=data, prompt=text, repo_path=repo_path, file_path=file_path)
        return self._invoke_model_with_logging(file_path, system, user)

    def generate_questions(self, text: str) -> str:
        system = self.prompts['system_message_question']
        user = self.prompts['prompt_question'].format(prompt=text)
        raw = self.bedrock_runtime.converse(
            modelId=constants.BEDROCK_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={
                "temperature": constants.LLM_MODEL_TEMPERATURE,
                "maxTokens": constants.LLM_MAX_TOKENS,
            },
        )
        try:
            content_blocks = raw["output"]["message"]["content"]
            text_parts = [b.get("text", "") for b in content_blocks if isinstance(b, dict)]
            return "\n".join([t for t in text_parts if t])
        except Exception:
            return json.dumps(raw, default=str)
    
    def _general_code_question(self, prompt_name: str, text: str) -> str:
        system = self.prompts[f'system_message_{prompt_name}']
        user = self.prompts[f'prompt_{prompt_name}'].format(code=text)
        raw = self.bedrock_runtime.converse(
            modelId=constants.BEDROCK_MODEL_ID,
            system=[{"text": system}],
            messages=[{"role": "user", "content": [{"text": user}]}],
            inferenceConfig={
                "temperature": constants.LLM_MODEL_TEMPERATURE,
                "maxTokens": constants.LLM_MAX_TOKENS,
            },
        )
        try:
            content_blocks = raw["output"]["message"]["content"]
            text_parts = [b.get("text", "") for b in content_blocks if isinstance(b, dict)]
            return "\n".join([t for t in text_parts if t])
        except Exception:
            return json.dumps(raw, default=str)
    
    def optimize_code_style(self, text: str) -> str:
        return self._general_code_question('optimize', text)

    def explain_code(self, text: str) -> str:
        return self._general_code_question('explain', text)

    def debug_code(self, text: str) -> str:
        return self._general_code_question('debug', text)
