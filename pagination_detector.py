import os
import json
from typing import List, Dict, Tuple, Union
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from groq import Groq

from assets import PROMPT_PAGINATION, GROQ_LLAMA_MODEL_FULLNAME

load_dotenv()
import logging

class PaginationData(BaseModel):
    page_urls: List[str] = Field(default_factory=list, description="List of pagination URLs, including 'Next' button URL if present")


def detect_pagination_elements(url: str, indications: str, markdown_content: str) -> Tuple[Union[PaginationData, Dict, str], Dict, float]:
    try:
        """
        Uses AI models to analyze markdown content and extract pagination elements.

        Args:
            selected_model (str): The name of the OpenAI model to use.
            markdown_content (str): The markdown content to analyze.

        Returns:
            Tuple[PaginationData, Dict, float]: Parsed pagination data
        """ 
        prompt_pagination = PROMPT_PAGINATION+"\n The url of the page to extract pagination from   "+url+"if the urls that you find are not complete combine them intelligently in a way that fit the pattern **ALWAYS GIVE A FULL URL**"
        if indications != "":
            prompt_pagination +=PROMPT_PAGINATION+"\n\n these are the users indications that, pay special attention to them: "+indications+"\n\n below are the markdowns of the website: \n\n"
        else:
            prompt_pagination +=PROMPT_PAGINATION+"\n There are no user indications in this case just apply the logic described. \n\n below are the markdowns of the website: \n\n"

        
        # Use Groq client
        client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
        response = client.chat.completions.create(
                model=GROQ_LLAMA_MODEL_FULLNAME,
                messages=[
                    {"role": "system", "content": prompt_pagination},
                    {"role": "user", "content": markdown_content},
                ],
        )
        response_content = response.choices[0].message.content.strip()
        # Try to parse the JSON
        try:
            pagination_data = json.loads(response_content)
        except json.JSONDecodeError:
            pagination_data = {"page_urls": []}
            
        # Ensure the pagination_data is a dictionary
        if isinstance(pagination_data, PaginationData):
            pagination_data = pagination_data.dict()
        elif not isinstance(pagination_data, dict):
            pagination_data = {"page_urls": []}

        return pagination_data 


    except Exception as e:
        logging.error(f"An error occurred in detect_pagination_elements: {e}")
