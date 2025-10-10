from __future__ import annotations

from typing import List
import json

from core.knowledgebase import constants
from core.knowledgebase.AWSAuth import AWSAuthenticator


class Embeddings:
    @staticmethod
    def get_embedding(text: str, model=constants.BEDROCK_EMBEDDING_MODEL) -> List[float]:
        """Get embeddings using AWS Bedrock embedding model."""
        text = text.replace("\n", " ")
        
        # Get authenticated Bedrock runtime client
        authenticator = AWSAuthenticator()
        bedrock_runtime = authenticator.get_bedrock_runtime_client()
        
        # Prepare the request body for Bedrock embedding
        request_body = {
            "inputText": text
        }
        
        try:
            # Call Bedrock embedding API
            response = bedrock_runtime.invoke_model(
                modelId=model,
                body=json.dumps(request_body),
                contentType='application/json',
                accept='application/json'
            )
            
            # Parse the response
            response_body = json.loads(response['body'].read())
            
            # Extract embedding vector (format depends on the embedding model)
            if 'embedding' in response_body:
                return response_body['embedding']
            elif 'embeddings' in response_body:
                return response_body['embeddings'][0]  # Assuming first embedding
            else:
                raise ValueError(f"Unexpected response format: {response_body}")
                
        except Exception as e:
            raise RuntimeError(f"Failed to get embeddings from Bedrock: {e}")


if __name__ == '__main__':
    print(Embeddings.get_embedding('bonaparte'))
