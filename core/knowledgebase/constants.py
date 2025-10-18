import os
import dotenv

f = dotenv.find_dotenv()
if not f:
    f = dotenv.find_dotenv('template.env')
dotenv.load_dotenv(f)

# AWS Authentication Configuration (priority order)
AWS_BEARER_TOKEN_BEDROCK = os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
AWS_PROFILE = os.environ.get("AWS_PROFILE")
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = os.environ.get("AWS_SESSION_TOKEN")

# AWS Bedrock Configuration
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
BEDROCK_EMBEDDING_MODEL = os.environ.get("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")

# Model Parameters
LLM_MODEL_TEMPERATURE = os.environ.get("LLM_MODEL_TEMPERATURE", "0.2")
LLM_MODEL_TEMPERATURE = float(LLM_MODEL_TEMPERATURE)
LLM_MAX_TOKENS = 8192

# Memgraph Configuration
MEMGRAPH_HOST = os.environ.get("MEMGRAPH_HOST", "127.0.0.1")
MEMGRAPH_PORT = os.environ.get("MEMGRAPH_PORT", "7687")
MEMGRAPH_PORT = int(MEMGRAPH_PORT)

# Chroma Configuration
CHROMA_DATA_DIR = os.environ.get("CHROMA_DATA_DIR")
CHROMA_VECTOR_SPACE = os.environ.get("CHROMA_VECTOR_SPACE")

# Prompts
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), 'prompts')

MOCK = (os.environ.get("MOCK", 'False') == 'True')
