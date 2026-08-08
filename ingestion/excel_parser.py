import pandas as pd


def parse_excel(uploaded_file):
    df = pd.read_excel(uploaded_file)
    return df