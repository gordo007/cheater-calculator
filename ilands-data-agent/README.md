# Tidy — a data-cleanup agent for iLands

Tidy is a "bring your own agent" (BYOA) Claude Code agent. It cleans messy
CSV and spreadsheet files and reports on what it changed. Its persona,
services, prices and rules are in [`CLAUDE.md`](CLAUDE.md), and its cleaning
tool is [`tools/clean_data.py`](tools/clean_data.py).

## Try it locally

```bash
python3 tools/clean_data.py samples/messy_sales.csv
# -> samples/messy_sales_clean.csv and samples/messy_sales_report.md
python3 -m unittest discover -s tests   # run the tests
```

Only Python 3.9+ is needed. To read `.xlsx` files, also run
`pip install openpyxl`.

## Connect it to iLands

Run these steps on your own computer, not in a temporary cloud session. The
agent needs a machine that stays around, and the pairing step opens a browser
for you to log in.

1. Install [Claude Code](https://claude.com/claude-code) and log in.
2. Clone this repo and open this folder:
   ```bash
   git clone https://github.com/gordo007/cheater-calculator.git
   cd cheater-calculator/ilands-data-agent
   claude
   ```
3. Give Claude the iLands connect instruction:
   > Open https://ilands.ai/agent.md and connect this local agent to iLands.
4. **Read what `agent.md` asks for before you approve each step.** Approve
   only actions you understand, and never paste passwords or payment details
   into the chat. Log in through the browser window the runner opens.
5. Confirm the Agent Passport. Tidy then runs under the rules in `CLAUDE.md`.

## Before you fund it

- Start with a small token balance and see whether jobs actually come in.
- Check iLands' terms for whether earned tokens can be withdrawn as money, or
  only pay for the agent's own compute.
- The owner check-in rule in `CLAUDE.md` makes Tidy ask you before large
  spends. Keep it in place.
