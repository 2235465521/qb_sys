import pandas as pd
import sys

try:
    df = pd.read_excel(r'E:\企标记录\batch-normative-ref-28-批次_25.xlsx')
    with open('scratch/excel_structure.txt', 'w', encoding='utf-8') as f:
        f.write("Columns:\n")
        f.write(", ".join(df.columns.tolist()) + "\n\n")
        f.write("Shape: {}\n\n".format(df.shape))
        f.write("Head rows:\n")
        f.write(df.head(15).to_string())
    print("Excel structural info exported to scratch/excel_structure.txt successfully.")
except Exception as e:
    print("Error reading Excel:", str(e))
