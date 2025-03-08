# pip install --force-reinstall torch --index-url https://download.pytorch.org/whl/cu118
# pip install --upgrade typing_extensions
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
from dotenv import load_dotenv
from datetime import datetime
import streamlit as st
import pandas as pd
import requests, os, torch
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# TODO
# - Adicionar todas as cidades no ITJOBS a uma combobox
# - Verificar uso legal de dados do ITJOBS
# - Adicionar traduções
# - Adicionar à tabela caso seja "Full-time", "Part-time"
# - Adicionar à tablea caso seja "Contrato", "Estágio", etc
# - Pesquisar descrições por detalhes 
# - Train own model to recognize TECHNOLOGIES and ROLES in Job Titles
# - 

st.set_page_config(page_icon="💻", page_title="ITJobs Analyzer")
st.title("ITJobs Analyzer 🕵️‍♂️💻")
st.caption("Use AI and Data Visualization techniques to search, analyze, and extract insight from Portugal's IT job market.")
st.markdown(
    """
    Powered by 
    <a href="https://www.itjobs.pt/" target="_blank">
        <img src="https://static.itjobs.pt/images/logo.png" alt="ITJobs" width="100">
    </a>
    """,
    unsafe_allow_html=True,
)

# Load the Hugging Face NER model
tokenizer = AutoTokenizer.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
model = AutoModelForTokenClassification.from_pretrained("dbmdz/bert-large-cased-finetuned-conll03-english")
ner_pipeline = pipeline("ner", model=model, tokenizer=tokenizer)

def extract_entities(text):
    """Extract named entities from text using the NER model."""
    entities = ner_pipeline(text)
    extracted_roles = set()
    extracted_techs = set()
    
    for entity in entities:
        label = entity['entity']
        word = entity['word']
        if "MISC" in label or "ORG" in label:  # Example: Organizations/Tech stacks often get labeled as MISC
            extracted_techs.add(word)
        elif "PER" in label:  # People/Job Roles sometimes get labeled as PER
            extracted_roles.add(word)
    
    return extracted_roles, extracted_techs

# Load environment variables (for API_KEY)
load_dotenv()
api_key = os.getenv("API_KEY")

# Function to format the date
def format_date(date_str):
    if date_str != "N/A":
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            return date_obj.strftime("%d-%m-%Y")
        except ValueError:
            return "N/A"
    return "N/A"

# Fetch all available cities and their respective location codes
def fetch_cities():
    url = "https://api.itjobs.pt/location/list.json"
    params = {
        "api_key": api_key
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # Raise an exception for any HTTP errors

        if response.status_code == 200:
            data = response.json()
            locations = data.get("results", [])
            # Create a dictionary with location names and their codes
            locations = {location["name"]: location["id"] for location in locations}
            return locations
        else:
            st.error(f"Failed to fetch locations. HTTP Status Code: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred: {e}")
        return {}

# Fetch job listings based on the selected location code
def fetch_all_jobs(location_code=None):
    url = "https://api.itjobs.pt/job/list.json"
    all_jobs = []
    page = 1
    limit = 100  # Maximum allowed per request

    while True:
        params = {
            "api_key": api_key,
            "limit": limit,
            "page": page,
            "state": 1,
        }

        if location_code:
            params["location"] = location_code  # Use the location code for the request

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }

        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            break

        data = response.json()
        jobs = data.get('results', [])

        if not jobs:
            break  # No more jobs to fetch

        all_jobs.extend(jobs)
        page += 1
    
    return all_jobs

# Fetch all available cities
locations = fetch_cities()
selected_location_name = st.selectbox("Select a location", ["All"] + list(locations.keys()))
selected_location_code = locations.get(selected_location_name)

# Fetch job listings based on the selected location code
jobs = fetch_all_jobs(location_code=selected_location_code if selected_location_name != "All" else None)

if jobs:

    job_offers = []
    company_counts = {}
    location_distribution = {}
    tech_distribution = {}
    role_distribution = {}

    for job in jobs:

        roles, techs = extract_entities(job["title"])
        for role in roles:
            role_distribution[role] = role_distribution.get(role, 0) + 1
        for tech in techs:
            tech_distribution[tech] = tech_distribution.get(tech, 0) + 1
        for location in job.get("locations", []):
            location_name = location["name"]
            location_distribution[location_name] = location_distribution.get(location_name, 0) + 1

        allow_remote = "✅" if job["allowRemote"] else "❌"
        job_offers.append({
            "Job Title": job["title"],
            "Company": job["company"]["name"],
            "Offer": f'<a href="https://www.itjobs.pt/oferta/{job["id"]}" target="_blank">🔗 Link</a>',
            "Date Posted": format_date(job.get("updatedAt", "N/A")),
            "Allow Remote": allow_remote,
        })

        # Count companies
        company_name = job["company"]["name"]
        company_counts[company_name] = company_counts.get(company_name, 0) + 1

    # Convert the list of job offers to a pandas DataFrame
    offers_df = pd.DataFrame(job_offers)

    # Remove the index column and make the table re-orderable
    st.write("###", len(jobs), "offer(s) found")
    st.dataframe(offers_df, use_container_width=True, hide_index=True)  # hide_index=True removes the index column

    # Display Company Offer Counts (sorted by number of offers)
    company_counts_df = pd.DataFrame(list(company_counts.items()), columns=["Company", "Number of Offers"])
    company_counts_df = company_counts_df.sort_values(by="Number of Offers", ascending=False)
    st.write("###", len(company_counts_df), " unique companies")
    st.dataframe(company_counts_df.style.hide(axis='index'), use_container_width=True, hide_index=True)  # Removed index

    # Location Distribution Bar Chart (only if "All" is selected)
    if selected_location_name == "All":
        st.write("### Location Distribution")
        location_df = pd.DataFrame(list(location_distribution.items()), columns=["Location", "Count"])
        location_df = location_df.sort_values(by="Count", ascending=False)
        st.bar_chart(location_df.set_index("Location"))

    # Remote vs Non-Remote job count
    remote_count = sum(1 for job in jobs if job["allowRemote"])
    non_remote_count = len(jobs) - remote_count

    # Show Remote vs Non-Remote bar chart
    st.write("### Remote vs Non-Remote Jobs")
    remote_vs_non_remote = pd.DataFrame({
        "Type": ["Remote", "Non-Remote"],
        "Count": [remote_count, non_remote_count]
    })
    st.bar_chart(remote_vs_non_remote.set_index("Type"))

    # Display results in Streamlit
    st.write("### Technology Distribution")
    st.bar_chart(pd.DataFrame.from_dict(tech_distribution, orient='index', columns=['Count']))

    st.write("### Role Distribution")
    st.bar_chart(pd.DataFrame.from_dict(role_distribution, orient='index', columns=['Count']))

else:
    st.warning("No jobs found.")
