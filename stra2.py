import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from typing import List, Tuple
import pyperclip
import re

def get_headings(url: str, keywords: List[str] = None) -> Tuple[int, dict, List[Tuple[str, str]], str, int, str, dict]:
    """
    Fetch the webpage and extract headings, title, HTTP status code, meta description, and keyword counts.
    Returns total count, per-level counts, list of (tag, text) for structure, page title, status code, meta description, and keyword counts.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        status_code = response.status_code
        soup = BeautifulSoup(response.text, 'html.parser')
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        page_title = soup.find('title').text.strip() if soup.find('title') else "No Title"
        
        meta_desc_tag = soup.find('meta', attrs={'name': 'description'})
        meta_desc = meta_desc_tag['content'].strip() if meta_desc_tag and 'content' in meta_desc_tag.attrs else "No Meta Description"
        
        counts = {'H1': 0, 'H2': 0, 'H3': 0, 'H4': 0, 'H5': 0, 'H6': 0}
        total = 0
        structure = []
        
        for h in headings:
            tag = h.name.upper()
            if tag in counts:
                counts[tag] += 1
                total += 1
                structure.append((tag, h.text.strip()))
        
        # Count keywords if provided
        keyword_counts = {}
        if keywords:
            text_content = soup.get_text().lower()
            for keyword in keywords:
                if keyword.strip():
                    # Count occurrences using regex for whole words
                    pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
                    count = len(re.findall(pattern, text_content))
                    keyword_counts[keyword] = count
        
        return total, counts, structure, page_title, status_code, meta_desc, keyword_counts
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching {url}: {str(e)}")
        return 0, {}, [], "Error", getattr(e.response, 'status_code', 0), "Error", {}

def build_tree(structure: List[Tuple[str, str]]) -> str:
    """
    Build a indented tree representation of headings.
    Uses indentation to show nesting based on levels.
    """
    if not structure:
        return "No headings found."
    
    tree = ""
    min_level = min(int(tag[1]) for tag, _ in structure) if structure else 1
    
    for tag, text in structure:
        level = int(tag[1]) - min_level
        indent = "  " * level
        tree += f"{indent}- {tag}: {text}\n"
    
    return tree

st.set_page_config(layout="centered")  # Centered layout to make input narrower
st.title("Heading Analyzer Tool")
st.markdown("Enter multiple URLs (one per line) or upload an Excel file with URLs in column A to analyze their headings. This tool fetches webpages, counts headings, provides a tree view with copy functionality, HTTP status, and meta description.")

# Text area for manual URLs
urls_input = st.text_area("URLs (one per line):", height=200)

# File uploader for Excel
uploaded_file = st.file_uploader("Upload Excel file (.xlsx):", type=["xlsx"])

# Keyword search option
enable_keyword_search = st.checkbox("Enable keyword search")

keywords = []
if enable_keyword_search:
    st.info("Enter up to 5 keywords to search for in the pages (one per line)")
    keyword_input = st.text_area("Keywords:", height=100, placeholder="Enter one keyword per line\nExample:\nseo\ndigital marketing\nweb analytics")
    if keyword_input:
        keywords = [k.strip() for k in keyword_input.split("\n") if k.strip()][:5]  # Limit to 5 keywords

if st.button("Analyze Headings"):
    urls = []
    
    # Process manual input
    if urls_input:
        urls = [u.strip() for u in urls_input.split("\n") if u.strip()]
    
    # Process uploaded Excel
    if uploaded_file:
        try:
            df_uploaded = pd.read_excel(uploaded_file)
            if 'A' in df_uploaded.columns:  # Assuming column A is labeled as 'A' or first column
                urls.extend(df_uploaded['A'].dropna().astype(str).tolist())
            else:
                st.warning("No column 'A' found in the Excel file. Using the first column instead.")
                urls.extend(df_uploaded.iloc[:, 0].dropna().astype(str).tolist())
            urls = list(set(urls))  # Remove duplicates if any
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")
    
    if not urls:
        st.warning("Please enter at least one URL or upload a valid Excel file.")
    else:
        data = []
        structures = {}
        
        with st.spinner("Analyzing URLs..."):
            for url in urls:
                total, counts, struct, page_title, status_code, meta_desc, keyword_counts = get_headings(url, keywords if enable_keyword_search else None)
                row = {
                    "URL": url,
                    "Title": page_title,
                    "HTTP Status": status_code,
                    "Meta Description": meta_desc,
                    "Total Headings": total,
                    "H1": counts.get("H1", 0),
                    "H2": counts.get("H2", 0),
                    "H3": counts.get("H3", 0),
                    "H4": counts.get("H4", 0),
                    "H5": counts.get("H5", 0),
                    "H6": counts.get("H6", 0)
                }
                
                # Add keyword counts to row if enabled
                if enable_keyword_search and keywords:
                    for keyword in keywords:
                        row[keyword] = keyword_counts.get(keyword, 0)
                
                data.append(row)
                structures[url] = struct
        
        st.session_state['results'] = {'data': data, 'structures': structures}

if 'results' in st.session_state and st.session_state['results'].get('data'):
    df = pd.DataFrame(st.session_state['results']['data'])
    st.subheader("Headings Summary Table")
    st.dataframe(df, use_container_width=True, height=400)  # Larger table height
    
    st.subheader("Tree Views")
    structures = st.session_state['results']['structures']
    for url in structures.keys():
        with st.expander(f"View Tree for {url}"):
            structure = structures.get(url, [])
            tree_text = build_tree(structure)
            st.code(tree_text, language="markdown")
            if st.button("Copy Full Tree", key=f"copy_full_{url}"):
                pyperclip.copy(tree_text)
                st.success("Copied full tree to clipboard!")