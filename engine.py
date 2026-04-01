import numpy as np
import pandas as pd
from dataclasses import dataclass
import copy

# ==========================================
# 1. DATA INPUT CLASSES
# ==========================================
@dataclass
class UserProfile:
    current_age: int
    target_retirement_age: int
    gross_salary: float
    living_expenses: float
    wage_growth_rate: float = 0.01
    inflation_rate: float = 0.015
    steuerfuss: float = 1.19
    current_3a_contribution: float = 0

@dataclass
class RealEstate:
    market_value: float
    steuerwert: float
    eigenmietwert: float
    mortgage_debt: float
    interest_rate: float
    amortization_type: str = "Direct" # "Direct" or "Indirect"
    maintenance_rate: float = 0.01

@dataclass
class PensionFund:
    obligatory_capital: float
    extra_obligatory_capital: float
    annual_contribution: float
    buy_in_potential: float = 0
    wef_balance: float = 0
    deckungsgrad: float = 1.05
    bvg_min_interest: float = 0.0125
    fund_verzinsung: float = 0.015
    umwandlungssatz_ob: float = 0.068
    umwandlungssatz_extra: float = 0.050

@dataclass
class Portfolio:
    balance: float
    weight_equities: float
    weight_bonds: float
    weight_cash: float
    number_of_accounts: int = 1
    eq_div_yield: float = 0.015
    eq_growth_mean: float = 0.05
    eq_growth_vol: float = 0.12
    bond_yield: float = 0.02
    cash_yield: float = 0.005

# ==========================================
# 2. ZURICH TAX CALCULATOR
# ==========================================
class ZurichTaxCalculator:
    def __init__(self, steuerfuss: float):
        self.steuerfuss = steuerfuss
        
    def calculate_income_tax(self, taxable_income: float) -> float:
        if taxable_income < 15000: return 0
        elif taxable_income < 100000: return (taxable_income - 15000) * 0.05 * self.steuerfuss
        else: return ((85000 * 0.05) + ((taxable_income - 100000) * 0.09)) * self.steuerfuss

    def calculate_wealth_tax(self, taxable_wealth: float) -> float:
        if taxable_wealth < 100000: return 0
        else: return (taxable_wealth - 100000) * 0.0015 * self.steuerfuss
    
    def calculate_capital_withdrawal_tax(self, lump_sum: float) -> float:
        return self.calculate_income_tax(lump_sum) * 0.2

# ==========================================
# 3. CORE SIMULATION
# ==========================================
class Simulation:
    def __init__(self, user, re, bvg, p3a, fw):
        self.user = user
        self.re = re
        self.bvg = bvg
        self.p3a = p3a
        self.fw = fw
        self.tax_calc = ZurichTaxCalculator(user.steuerfuss)
        self.ahv_pension = 29400

    def run_iteration(self, take_bvg_lump_sum=False):
        history = []
        age = self.user.current_age
        salary = self.user.gross_salary
        expenses = self.user.living_expenses
        bvg_pension_payout = 0
        
        while age <= 90:
            year_data = {'Age': age}
            eq_return = np.random.normal(self.fw.eq_growth_mean, self.fw.eq_growth_vol)
            
            # PHASE 1: ACCUMULATION
            if age < self.user.target_retirement_age:
                fw_taxable_yield = self.fw.balance * ((self.fw.weight_equities * self.fw.eq_div_yield) + (self.fw.weight_bonds * self.fw.bond_yield) + (self.fw.weight_cash * self.fw.cash_yield))
                mortgage_interest = self.re.mortgage_debt * self.re.interest_rate
                maintenance = self.re.market_value * self.re.maintenance_rate
                p3a_contribution = self.user.current_3a_contribution
                
                taxable_income = salary + self.re.eigenmietwert + fw_taxable_yield - mortgage_interest - maintenance - p3a_contribution
                income_tax = self.tax_calc.calculate_income_tax(max(0, taxable_income))
                
                taxable_wealth = self.fw.balance + self.re.steuerwert - self.re.mortgage_debt
                wealth_tax = self.tax_calc.calculate_wealth_tax(max(0, taxable_wealth))
                
                free_cash_flow = salary - expenses - income_tax - wealth_tax - mortgage_interest - p3a_contribution
                
                self.fw.balance += free_cash_flow + (self.fw.balance * (self.fw.weight_equities * eq_return)) + fw_taxable_yield
                self.p3a.balance += p3a_contribution + (self.p3a.balance * ((self.p3a.weight_equities * (eq_return + self.p3a.eq_div_yield)) + (self.p3a.weight_bonds * self.p3a.bond_yield)))
                
                self.bvg.obligatory_capital += (self.bvg.obligatory_capital * self.bvg.bvg_min_interest) + (self.bvg.annual_contribution * 0.5)
                self.bvg.extra_obligatory_capital += (self.bvg.extra_obligatory_capital * self.bvg.fund_verzinsung) + (self.bvg.annual_contribution * 0.5)
                
                salary *= (1 + self.user.wage_growth_rate)
                expenses *= (1 + self.user.inflation_rate)

            # PHASE 2: RETIREMENT EVENT
            elif age == self.user.target_retirement_age:
                bvg_potential_pension = (self.bvg.obligatory_capital * self.bvg.umwandlungssatz_ob) + (self.bvg.extra_obligatory_capital * self.bvg.umwandlungssatz_extra)
                stress_costs = (self.re.mortgage_debt * 0.05) + (self.re.market_value * 0.01)
                
                if stress_costs > ((self.ahv_pension + bvg_potential_pension) * 0.33):
                    payoff_amount = min(self.re.mortgage_debt, (stress_costs - ((self.ahv_pension + bvg_potential_pension) * 0.33)) / 0.05)
                    self.re.mortgage_debt -= payoff_amount
                    self.fw.balance -= payoff_amount

                p3a_tax = self.tax_calc.calculate_capital_withdrawal_tax(self.p3a.balance)
                self.fw.balance += (self.p3a.balance - p3a_tax)
                self.p3a.balance = 0
                
                if take_bvg_lump_sum:
                    total_bvg = self.bvg.obligatory_capital + self.bvg.extra_obligatory_capital
                    bvg_tax = self.tax_calc.calculate_capital_withdrawal_tax(total_bvg)
                    self.fw.balance += (total_bvg - bvg_tax)
                else:
                    bvg_pension_payout = bvg_potential_pension

            # PHASE 3: DECUMULATION
            if age >= self.user.target_retirement_age:
                mortgage_interest = self.re.mortgage_debt * self.re.interest_rate
                maintenance = self.re.market_value * self.re.maintenance_rate
                
                taxable_income = self.ahv_pension + bvg_pension_payout + self.re.eigenmietwert - mortgage_interest - maintenance
                income_tax = self.tax_calc.calculate_income_tax(max(0, taxable_income))
                wealth_tax = self.tax_calc.calculate_wealth_tax(max(0, self.fw.balance + self.re.steuerwert - self.re.mortgage_debt))
                
                shortfall = expenses - (self.ahv_pension + bvg_pension_payout - income_tax - wealth_tax - mortgage_interest - maintenance)
                
                if shortfall > 0: self.fw.balance -= shortfall
                    
                if self.fw.balance < 0 and self.re.market_value > 0: # Downsize Trigger
                    self.fw.balance += (self.re.market_value - self.re.mortgage_debt)
                    self.re.market_value = 0
                    self.re.eigenmietwert = 0
                    self.re.mortgage_debt = 0
                    expenses += 36000

                if self.fw.balance > 0:
                    fw_taxable_yield = self.fw.balance * (self.fw.weight_equities * self.fw.eq_div_yield + self.fw.weight_bonds * self.fw.bond_yield)
                    self.fw.balance += (self.fw.balance * (self.fw.weight_equities * eq_return)) + fw_taxable_yield
                
                expenses *= (1 + self.user.inflation_rate)

            year_data['Net_Worth'] = self.fw.balance + self.p3a.balance + (self.re.market_value - self.re.mortgage_debt)
            year_data['Free_Wealth'] = self.fw.balance
            history.append(year_data)
            age += 1
            
        return pd.DataFrame(history)

# ==========================================
# 4. ACTION PLAN GENERATOR (THE BRAIN)
# ==========================================
class ActionPlanGenerator:
    def __init__(self, user, re, bvg, p3a, fw, baseline_df, lump_sum_better, p_fail):
        self.user = user
        self.re = re
        self.bvg = bvg
        self.p3a = p3a
        self.fw = fw
        self.baseline_df = baseline_df
        self.lump_sum_better = lump_sum_better
        self.p_fail = p_fail
        self.years_to_ret = self.user.target_retirement_age - self.user.current_age
        self.actions = []

    def generate_plan(self):
        # 1. Low Hanging Fruit (Pillar 3a & Cash)
        if self.user.current_3a_contribution < 7056:
            self.actions.append({"title": "Maximize Pillar 3a", "description": "Increase your 3a contribution to CHF 7,056 for an immediate ~20-30% tax return in Zurich."})
        if self.p3a.weight_cash > 0.3 and self.years_to_ret > 7:
            self.actions.append({"title": "Eliminate 3a Cash Drag", "description": "Shift your 3a cash into Equities. Capital gains in 3a are tax-free, making it the best place for growth."})
        if self.fw.weight_cash > 0.4:
            self.actions.append({"title": "Put Savings to Work", "description": "Too much of your wealth is in cash losing to inflation. Invest it; Swiss capital gains are 100% tax-free."})
        
        # 2. Structure & Tax Arbitrage
        if self.fw.weight_bonds > 0 and self.p3a.weight_equities > 0:
            self.actions.append({"title": "Asset Location Swap", "description": "Swap your assets. Hold taxable Bonds in your tax-sheltered Pillar 3a, and hold tax-free Equities in your Free Wealth."})
        if self.re.amortization_type == 'Direct' and self.re.mortgage_debt > 0:
            self.actions.append({"title": "Stop Direct Amortization", "description": "Switch to 'Indirect Amortization' via Pillar 3a to keep your mortgage tax-deduction high while getting the 3a benefit."})
        
        # 3. Timing & Progression
        if getattr(self.p3a, 'number_of_accounts', 1) < 5 and self.p3a.balance > 20000:
            self.actions.append({"title": "Open Multiple 3a Accounts", "description": "Open up to 5 Pillar 3a accounts and withdraw them in different years (Age 61-65) to break Zurich's progressive tax curve."})
        if self.re.market_value > 0:
            self.actions.append({"title": "Smart Home Renovations", "description": "Take the 20% flat maintenance deduction for 3 years, then bunch renovations into one year, splitting invoices over Dec/Jan to break tax progression twice."})

        # 4. Legal Traps & Pension
        if self.bvg.wef_balance > 0:
            self.actions.append({"title": "⚠️ Repay WEF Withdrawal", "description": "You are legally barred from making tax-deductible pension buy-ins until your WEF withdrawal is repaid."})
        elif self.bvg.buy_in_potential > 20000 and (self.fw.balance * self.fw.weight_cash) > 20000:
            self.actions.append({"title": "Staggered Pension Buy-ins", "description": "You have excess cash and buy-in potential. Buy in over 3 years (e.g., CHF 15k/yr) to continuously shave off your highest tax bracket."})
        if self.years_to_ret <= 3 and self.lump_sum_better and self.bvg.buy_in_potential > 0:
            self.actions.append({"title": "⚠️ The 3-Year Rule Warning", "description": "Taking a lump sum is best for you. Do NOT make any voluntary pension buy-ins now, or you are legally blocked from taking a lump sum for 3 years."})
        
        if self.lump_sum_better:
            self.actions.append({"title": "Pension Payout: Lump Sum", "description": f"Taking a lump sum outperforms the guaranteed pension. Pay the one-time withdrawal tax and invest the capital."})
        
        if self.p_fail > 10.0:
            self.actions.append({"title": "⚠️ Real Estate Affordability Risk", "description": f"There is a {self.p_fail:.1f}% chance you fail the bank stress test in retirement. Build liquidity immediately."})

        return self.actions

# ==========================================
# 5. THE MAIN EXECUTOR (API ENTRY POINT)
# ==========================================
def run_financial_plan(data_dict):
    """This function is called by your API. It reads the frontend data and returns JSON."""
    
    # 1. Parse Data
    u = UserProfile(current_age=data_dict['age'], target_retirement_age=data_dict['ret_age'], gross_salary=data_dict['salary'], living_expenses=data_dict['expenses'], current_3a_contribution=data_dict['p3a_contrib'])
    re = RealEstate(market_value=data_dict['re_value'], steuerwert=data_dict['re_tax_value'], eigenmietwert=data_dict['re_rent'], mortgage_debt=data_dict['mortgage'], interest_rate=data_dict['interest'], amortization_type=data_dict['amortization'])
    bvg = PensionFund(obligatory_capital=data_dict['bvg_ob'], extra_obligatory_capital=data_dict['bvg_ex'], annual_contribution=data_dict['bvg_contrib'], buy_in_potential=data_dict['buy_in'], wef_balance=data_dict['wef'])
    
    p3a_base = Portfolio(balance=data_dict['p3a_bal'], weight_equities=data_dict['p3a_eq'], weight_bonds=data_dict['p3a_bond'], weight_cash=data_dict['p3a_cash'], number_of_accounts=data_dict['p3a_accounts'])
    fw_base = Portfolio(balance=data_dict['fw_bal'], weight_equities=data_dict['fw_eq'], weight_bonds=data_dict['fw_bond'], weight_cash=data_dict['fw_cash'])

    # 2. Run Monte Carlo Simulations
    iterations = 100
    base_results = []
    opt_results = []
    
    # Run a single baseline to get the dataframe for Action Plan analysis
    sim_base = Simulation(copy.deepcopy(u), copy.deepcopy(re), copy.deepcopy(bvg), copy.deepcopy(p3a_base), copy.deepcopy(fw_base))
    baseline_df = sim_base.run_iteration(take_bvg_lump_sum=False)

    for _ in range(iterations):
        sim1 = Simulation(copy.deepcopy(u), copy.deepcopy(re), copy.deepcopy(bvg), copy.deepcopy(p3a_base), copy.deepcopy(fw_base))
        base_results.append(sim1.run_iteration(take_bvg_lump_sum=False).iloc[-1]['Net_Worth'])
        
        sim2 = Simulation(copy.deepcopy(u), copy.deepcopy(re), copy.deepcopy(bvg), copy.deepcopy(p3a_base), copy.deepcopy(fw_base))
        opt_results.append(sim2.run_iteration(take_bvg_lump_sum=True).iloc[-1]['Net_Worth'])

    # 3. Analyze Results
    med_base = float(np.median(base_results))
    med_opt = float(np.median(opt_results))
    p_fail = float(np.mean(np.array(base_results) < 0) * 100)
    
    # 4. Generate Action Plan
    planner = ActionPlanGenerator(u, re, bvg, p3a_base, fw_base, baseline_df, med_opt > med_base, p_fail)
    actions = planner.generate_plan()

    # 5. Return JSON to Lovable
    return {
        "baseline_net_worth_90": round(med_base, 0),
        "optimized_net_worth_90": round(med_opt, 0),
        "wealth_gained": round(max(0, med_opt - med_base), 0),
        "probability_of_failure": round(p_fail, 1),
        "actions": actions
    }