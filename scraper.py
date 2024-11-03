import os
import random
import time
import re
import json
from datetime import datetime
from typing import List
import pandas as pd
from bs4 import BeautifulSoup
import html2text
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from groq import Groq


from assets import HEADLESS_OPTIONS,USER_MESSAGE,GROQ_LLAMA_MODEL_FULLNAME
load_dotenv()


def setup_selenium():
    options = Options()

    # Add other options
    for option in HEADLESS_OPTIONS:
        options.add_argument(option)


    # Initialize the WebDriver
    driver = webdriver.Chrome(options=options)
    return driver

def click_accept_cookies(driver):
    """
    Tries to find and click on a cookie consent button. It looks for several common patterns.
    """
    try:
        # Wait for cookie popup to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//button | //a | //div"))
        )
        
        # Common text variations for cookie buttons
        accept_text_variations = [
            "accept", "agree", "allow", "consent", "continue", "ok", "I agree", "got it"
        ]
        
        # Iterate through different element types and common text variations
        for tag in ["button", "a", "div"]:
            for text in accept_text_variations:
                try:
                    # Create an XPath to find the button by text
                    element = driver.find_element(By.XPATH, f"//{tag}[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{text}')]")
                    if element:
                        element.click()
                        print(f"Clicked the '{text}' button.")
                        return
                except:
                    continue

        print("No 'Accept Cookies' button found.")
    
    except Exception as e:
        print(f"Error finding 'Accept Cookies' button: {e}")

def scroll_to_load_full_page(driver, scroll_pause_time=2, max_attempts=10):
    """Scroll to the end of the page until all dynamic content is loaded."""
    
    last_height = driver.execute_script("return document.body.scrollHeight")  # Get initial scroll height
    attempts = 0  # Counter for failed attempts (in case content stops loading)
    
    while attempts < max_attempts:
        # Scroll down by a fraction of the page height (you can adjust this if needed)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Pause to allow dynamic content to load
        time.sleep(random.uniform(1.1, 1.8))  # Pause with random sleep to simulate human behavior
        
        # Calculate new scroll height after scrolling
        new_height = driver.execute_script("return document.body.scrollHeight")
        
        # Check if the page has loaded new content (if scroll height has changed)
        if new_height == last_height:
            attempts += 1  # Increment the failed attempts counter
        else:
            attempts = 0  # Reset attempts if new content is loaded
        
        # Update last height for the next iteration
        last_height = new_height
    
    # After scrolling is complete and no new content is loading, return the HTML
    html = driver.page_source
    return html

def fetch_html_selenium(url):
    driver = setup_selenium()
    try:
        driver.get(url)
        
        time.sleep(2)  
        driver.maximize_window()
        

        # Try to find and click the 'Accept Cookies' button
        click_accept_cookies(driver)

        return scroll_to_load_full_page(driver)
    finally:
        driver.quit()

def clean_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Remove headers and footers based on common HTML tags or classes
    for element in soup.find_all(['header', 'footer']):
        element.decompose()  # Remove these tags and their content

    return str(soup)


def html_to_markdown_with_readability(html_content):

    
    cleaned_html = clean_html(html_content)  
    
    # Convert to markdown
    markdown_converter = html2text.HTML2Text()
    markdown_converter.ignore_links = False
    markdown_content = markdown_converter.handle(cleaned_html)
    
    return markdown_content


    
def save_raw_data(raw_data: str, output_folder: str, file_name: str):
    """Save raw markdown data to the specified output folder."""
    os.makedirs(output_folder, exist_ok=True)
    raw_output_path = os.path.join(output_folder, file_name)
    with open(raw_output_path, 'w', encoding='utf-8') as f:
        f.write(raw_data)
    print(f"Raw data saved to {raw_output_path}")
    return raw_output_path


def remove_urls_from_file(file_path):
    # Regex pattern to find URLs
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'

    # Construct the new file name
    base, ext = os.path.splitext(file_path)
    new_file_path = f"{base}_cleaned{ext}"

    # Read the original markdown content
    with open(file_path, 'r', encoding='utf-8') as file:
        markdown_content = file.read()

    # Replace all found URLs with an empty string
    cleaned_content = re.sub(url_pattern, '', markdown_content)

    # Write the cleaned content to a new file
    with open(new_file_path, 'w', encoding='utf-8') as file:
        file.write(cleaned_content)
    print(f"Cleaned file saved as: {new_file_path}")
    return cleaned_content


def generate_system_message(fields) -> str:
    """
    Dynamically generate a system message based on the fields in the provided listing model.
    """

    # Extract field descriptions from the schema
    field_descriptions = []
    for field_name in fields:
        # Get the field type from the schema info
        field_descriptions.append(f'"{field_name}"')

    # Create the JSON schema structure for the listings
    schema_structure = ",\n".join(field_descriptions)

    # Generate the system message dynamically
    system_message = f"""
    You are an intelligent text extraction and conversion assistant. Your task is to extract structured information 
                        from the given text and convert it into a pure JSON format. The JSON should contain only the structured data extracted from the text, 
                        with no additional commentary, explanations, or extraneous information. 
                        You could encounter cases where you can't find the data of the fields you have to extract or the data will be in a foreign language.
                        Please process the following text and provide the output in pure JSON format with no words before or after the JSON:
    Please ensure the output strictly follows this schema:

    {{
        "listings": [
            {{
                {schema_structure}
            }}
        ]
    }} """

    return system_message



def format_data(data, fields):
    # Dynamically generate the system message based on the schema
    sys_message = generate_system_message(fields)
    # print(SYSTEM_MESSAGE)
    # Point to the local server
    client = Groq(api_key=os.environ.get("GROQ_API_KEY"),)

    completion = client.chat.completions.create(
    messages=[
            {"role": "system","content": sys_message},
            {"role": "user","content": USER_MESSAGE + data}
    ],
    model=GROQ_LLAMA_MODEL_FULLNAME,
    )

    # Extract the content from the response
    response_content = completion.choices[0].message.content
        
    # Convert the content from JSON string to a Python dictionary
    parsed_response = json.loads(response_content)
        
    return parsed_response
    



def save_formatted_data(formatted_data, output_folder: str, json_file_name: str, excel_file_name: str):
    """Save formatted data as JSON and Excel in the specified output folder."""
    os.makedirs(output_folder, exist_ok=True)
    
    # Parse the formatted data if it's a JSON string (from Gemini API)
    if isinstance(formatted_data, str):
        try:
            formatted_data_dict = json.loads(formatted_data)
        except json.JSONDecodeError:
            raise ValueError("The provided formatted data is a string but not valid JSON.")
    else:
        # Handle data from OpenAI or other sources
        formatted_data_dict = formatted_data.dict() if hasattr(formatted_data, 'dict') else formatted_data

    # Save the formatted data as JSON
    json_output_path = os.path.join(output_folder, json_file_name)
    with open(json_output_path, 'w', encoding='utf-8') as f:
        json.dump(formatted_data_dict, f, indent=4)
    print(f"Formatted data saved to JSON at {json_output_path}")

    # Prepare data for DataFrame
    if isinstance(formatted_data_dict, dict):
        # If the data is a dictionary containing lists, assume these lists are records
        data_for_df = next(iter(formatted_data_dict.values())) if len(formatted_data_dict) == 1 else formatted_data_dict
    elif isinstance(formatted_data_dict, list):
        data_for_df = formatted_data_dict
    else:
        raise ValueError("Formatted data is neither a dictionary nor a list, cannot convert to DataFrame")

    # Create DataFrame
    try:
        df = pd.DataFrame(data_for_df)
        print("DataFrame created successfully.")

        # Save the DataFrame to an Excel file
        excel_output_path = os.path.join(output_folder, excel_file_name)
        df.to_excel(excel_output_path, index=False)
        print(f"Formatted data saved to Excel at {excel_output_path}")
        
        return df
    except Exception as e:
        print(f"Error creating DataFrame or saving Excel: {str(e)}")
        return None


def generate_unique_folder_name(url):
    timestamp = datetime.now().strftime('%Y_%m_%d__%H_%M_%S')
    url_name = re.sub(r'\W+', '_', url.split('//')[1].split('/')[0])  # Extract domain name and replace non-alphanumeric characters
    return f"{url_name}_{timestamp}"


def scrape_multiple_urls(urls, fields, selected_model):
    output_folder = os.path.join('output', generate_unique_folder_name(urls[0]))
    os.makedirs(output_folder, exist_ok=True)
    
    all_data = []
    markdown = None  # We'll store the markdown for the first (or only) URL
    
    for i, url in enumerate(urls, start=1):
        raw_html = fetch_html_selenium(url)
        current_markdown = html_to_markdown_with_readability(raw_html)
        if i == 1:
            markdown = current_markdown  # Store markdown for the first URL
        
        formatted_data = scrape_url(url, fields, selected_model, output_folder, i, current_markdown)
        all_data.append(formatted_data)
    
    return output_folder, all_data, markdown

def scrape_url(url: str, fields: List[str], output_folder: str, file_number: int, markdown: str):
    """Scrape a single URL and save the results."""
    print("fields = ", fields)
    try:
        # Save raw data
        save_raw_data(markdown, output_folder, f'rawData_{file_number}.md')

        # Format data
        formatted_data = format_data(markdown, fields)
        
        # Save formatted data
        save_formatted_data(formatted_data, output_folder, f'sorted_data_{file_number}.json', f'sorted_data_{file_number}.xlsx')

        return  formatted_data

    except Exception as e:
        print(f"An error occurred while processing {url}: {e}")
        return None
