import re


class BedrockResponseParser:
    """
    A parser to extract and clean content from AWS Bedrock Chat model responses.
    """

    @staticmethod
    def parse_cypher_from_message(message_or_text) -> str:
        """
        Extracts the string content from an AIMessage and cleans it to get a pure Cypher query.

        Args:
            message: The AIMessage object returned by the ChatBedrock model.

        Returns:
            A clean string containing only the Cypher query.
        """
        if isinstance(message_or_text, str):
            raw_content = message_or_text
        else:
            # Fallback for objects with 'content' attribute (e.g., AIMessage)
            try:
                raw_content = getattr(message_or_text, 'content', '')
                if not isinstance(raw_content, str):
                    raw_content = str(raw_content)
            except Exception:
                raw_content = str(message_or_text)

        # Regex to find content within ```cypher ... ``` or ``` ... ```
        match = re.search(r"```(?:cypher)?\s*\n(.*?)\n```", raw_content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        
        # Fallback for responses that might not have the markdown block but are just the query
        return raw_content.strip()
