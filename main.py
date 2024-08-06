import os
import re
import urllib.parse
from typing import List
from urllib.parse import urlparse, urljoin

# Third party
import requests
import tiktoken
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from llama_index.core.node_parser import TokenTextSplitter


class InputInfo:
    def __init__(self, name: str, type: str):
        self.name = name
        self.type = type


class FormInfo:
    def __init__(self, action: str):
        self.name = "(no name)"
        self.action = action
        self.method = "GET"
        self.inputs = []

    def add_input(self, input: InputInfo):
        self.inputs.append(input)

    def clean_inputs(self):
        for i in self.inputs:
            if i.type == "search":
                self.inputs = [i]
                return
        for i in self.inputs:
            if "search" in i.name.lower():
                self.inputs = [i]
                return


def parse_url(link: str, parsed_link: urllib.parse.ParseResult) -> (str, List[str], List[FormInfo]):
    try:
        resp = requests.get(link)
        if resp.status_code != 200:
            print(f"unexpected status code when getting {link}: {resp.status_code}")
            exit(0)

        links = []
        formInfos = []
        # Filter and parse HTML
        soup = BeautifulSoup(resp.text, "html.parser")
        # Update relative URLs to absolute URLs
        for a_tag in soup.find_all("a", href=True):
            a_tag["href"] = urljoin(link, a_tag["href"])
            parsed_href = urlparse(a_tag["href"])
            if parsed_href.hostname.endswith(parsed_link.hostname):
                links.append(a_tag["href"])

        # Gather information about forms
        for form_tag in soup.find_all("form", action=True):
            if "action" not in form_tag.attrs:
                continue

            form_info = FormInfo(form_tag["action"])
            if "id" in form_tag.attrs:
                form_info.name = form_tag["id"]
            if "method" in form_tag.attrs:
                form_info.method = form_tag["method"]

            for input_tag in form_tag.find_all("input"):
                if "name" not in input_tag.attrs or "type" not in input_tag.attrs:
                    continue
                form_info.add_input(InputInfo(input_tag["name"], input_tag["type"]))

            form_info.clean_inputs()
            formInfos.append(form_info)

        # Remove unwanted tags like 'script', 'style', etc.
        for script in soup(["script", "style", "noscript"]):
            script.extract()
        filtered_html = str(soup)

        # Convert HTML to Markdown
        html = md(filtered_html)

        # Remove consecutive newlines and return
        return re.sub(r"\n+", "\n", html).strip(), links, formInfos
    except Exception as e:
        print(f"Error in parse_url: {e}")
        exit(0)


# Begin execution

link = os.getenv("URL")
if link is None:
    print("please provide a URL")
    exit(1)
parsed_link = urlparse(link)

splitter = TokenTextSplitter(
    chunk_size=15000,
    chunk_overlap=10,
    tokenizer=tiktoken.encoding_for_model("gpt-4").encode)

siteText, links, formInfos = parse_url(link, parsed_link)

print(splitter.split_text(siteText)[0])
print("\nLinks:")
for url in links:
    print("- " + url)
# print("\nForms:")
# for form in formInfos:
#     print(f"- name: {form.name}")
#     print(f"  {form.method.upper()} {urljoin(link, form.action)}")
#     print("  inputs:")
#     for input in form.inputs:
#         print(f"  - {input.name} (type: {input.type})")
