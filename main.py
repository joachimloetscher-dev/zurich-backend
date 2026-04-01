from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from engine import run_financial_plan

app = FastAPI()

# This allows Lovable to talk to your API without security blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# This defines the data Lovable will send
class UserInput(BaseModel):
    age: int; ret_age: int; salary: float; expenses: float; p3a_contrib: float
    re_value: float; re_tax_value: float; re_rent: float; mortgage: float; interest: float; amortization: str
    bvg_ob: float; bvg_ex: float; bvg_contrib: float; buy_in: float; wef: float
    p3a_bal: float; p3a_eq: float; p3a_bond: float; p3a_cash: float; p3a_accounts: int
    fw_bal: float; fw_eq: float; fw_bond: float; fw_cash: float

@app.post("/calculate")
def calculate_plan(data: UserInput):
    # Pass data to our engine and return the result to Lovable!
    result = run_financial_plan(data.dict())
    return result