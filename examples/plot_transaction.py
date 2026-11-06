"""Demonstration chart only. No actual case data. Requires matplotlib, pandas."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
base = Path(__file__).resolve().parent
frame = pd.read_csv(base / 'transaction_demo.csv')
plt.figure(figsize=(7, 4))
plt.bar(frame['date'], frame['amount_krw'])
plt.ylabel('KRW')
plt.xlabel('Date (synthetic)')
plt.title('SYNTHETIC DATA — NOT EVIDENCE')
plt.ylim(bottom=0)
plt.tight_layout()
plt.savefig(base / 'transaction_demo.png', dpi=160)
print('wrote', base / 'transaction_demo.png')
