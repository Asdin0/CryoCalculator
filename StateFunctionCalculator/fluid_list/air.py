import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
path_to_A = os.path.join(project_root, 'general_class')
sys.path.insert(0, path_to_A)

import sympy as sy
import functools
import math as mth
import GeneralClass
import models

class Air(GeneralClass.RealFluid):
    def __init__(self):
        constants=models.FluidConstants(molar_mass_kg_mol=0.0289586,   
                                    critical_temperature_K=132.5306,
                                    critical_pressure_Pa=3786000,
                                    critical_density_kg_m3=342.60340488,
                                    reference_temperature_K=132.6312,
                                    reference_pressure_Pa=3785000,
                                    reference_density_kg_m3=302.5508,
                                    melting_temperature_K=59.75,
                                    melting_pressure_Pa=5265,
                                    acentric_factor=0.0353)
        
        saturation_terms=models.SaturationTerms(d_p_p=(-0.1567266,-5.539635,0.7567212,-3.514322),
                                        d_p_d=(-2.0466,-4.7520,-13.259,-47.652),
                                        b_p_d=(44.3413,-240.073,285.139,-88.3366,-0.892181),
                                        b_p_p=(0.2260724,-7.080499,5.700283,-12.44017,17.81926,-10.81364))
        
        ideal_helmholtz_terms=models.IdealHelmholtzTerms(e=(0.00000006057194,-0.0000210274769,-0.000158860716,-13.841928076,17.275266575,-0.00019536342,2.490888032,0.791309509,0.212236768,-0.197938904,25.36365,16.90741,87.31279))
        
        real_helmholtz_terms=((models.RealHelmholtzTerms(n=0.118160747229,i=1,j=0,l=0)),
                                 (models.RealHelmholtzTerms(n=0.713116392079,i=1,j=0.33,l=0)),
                                 (models.RealHelmholtzTerms(n=-1.61824192067,i=1,j=1.01,l=0)),
                                 (models.RealHelmholtzTerms(n=0.0714140178971,i=2,j=0,l=0)),
                                 (models.RealHelmholtzTerms(n=-0.0865421396646,i=3,j=0,l=0)),
                                 (models.RealHelmholtzTerms(n=0.134211176704,i=3,j=0.15,l=0)),
                                 (models.RealHelmholtzTerms(n=0.0112626704218,i=4,j=0,l=0)),
                                 (models.RealHelmholtzTerms(n=-0.0420533228842,i=4,j=0.2,l=0)),
                                 (models.RealHelmholtzTerms(n=0.0349008431982,i=4,j=0.35,l=0)),
                                 (models.RealHelmholtzTerms(n=0.000164957183186,i=6,j=1.35,l=0)),
                                 (models.RealHelmholtzTerms(n=-0.101365037912,i=1,j=1.6,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.17381369097,i=3,j=0.8,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.0472103183731,i=5,j=0.95,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.0122523554253,i=6,j=1.25,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.146629609713,i=1,j=3.6,l=2)),
                                 (models.RealHelmholtzTerms(n=-0.0316055879821,i=3,j=6,l=2)),
                                 (models.RealHelmholtzTerms(n=0.000233594806142,i=11,j=3.25,l=2)),
                                 (models.RealHelmholtzTerms(n=0.0148287891978,i=1,j=3.5,l=3)),
                                 (models.RealHelmholtzTerms(n=-0.00938782884667,i=3,j=15,l=3)))
        
        acceptable_parameters=models.AcceptableParameters(T_maximum_value_K=2000,T_minimum_value_K=60,P_maximum_value_Pa=2000000000,P_minimum_value_Pa=1)
        super().__init__(constants, saturation_terms, ideal_helmholtz_terms, real_helmholtz_terms, acceptable_parameters)

    def dewpoint_pressure(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            dewpoint_pressure=((mth.exp((self.constants.reference_temperature_K/t)*((self.saturation_terms.d_p_p[0]*teta**(1/2))+(self.saturation_terms.d_p_p[1]*teta**(1))+(self.saturation_terms.d_p_p[2]*teta**(5/2))+(self.saturation_terms.d_p_p[3]*teta**(8/2)))))*self.constants.reference_pressure_Pa)
        else:
            dewpoint_pressure=None
        return dewpoint_pressure

    def dewpoint_density(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            dewpoint_density=(mth.exp((self.saturation_terms.d_p_d[0]*teta**(0.41))+(self.saturation_terms.d_p_d[1]*teta**(1))+(self.saturation_terms.d_p_d[2]*teta**(2.8))+(self.saturation_terms.d_p_d[3]*teta**(6.5)))*self.constants.reference_density_kg_m3)  
        else:
            dewpoint_density=None
        return dewpoint_density
    
    def bubblepoint_pressure(self, t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            bubblepoint_pressure=((mth.exp((self.constants.reference_temperature_K/t)*((self.saturation_terms.b_p_p[0]*teta**(1/2))+(self.saturation_terms.b_p_p[1]*teta**(1))+(self.saturation_terms.b_p_p[2]*teta**(3/2))+(self.saturation_terms.b_p_p[3]*teta**(4/2))+(self.saturation_terms.b_p_p[4]*teta**(5/2))+(self.saturation_terms.b_p_p[5]*teta**(6/2)))))*self.constants.reference_pressure_Pa)
        else:
            bubblepoint_pressure=None
        return bubblepoint_pressure

    def bubblepoint_density(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            bubblepoint_density=((((self.saturation_terms.b_p_d[0]*teta**(0.65))+(self.saturation_terms.b_p_d[1]*teta**(0.85))+(self.saturation_terms.b_p_d[2]*teta**(0.95))+(self.saturation_terms.b_p_d[3]*teta**(1.1))+(self.saturation_terms.b_p_d[4]*mth.log(t/self.constants.reference_temperature_K)))+1)*self.constants.reference_density_kg_m3)
        else:
            bubblepoint_density=None
        return bubblepoint_density
    
    def meltingpoint_pressure(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            meltingpoint_pressure=((35493.5*((t/self.constants.melting_temperature_K)**(1.78963) -1)+1)*self.constants.melting_pressure_Pa)
        else:
            meltingpoint_pressure=None
        return meltingpoint_pressure
    
    @functools.cache
    def _reduced_ideal_helmholtzenergy_(self):
        t_r,d_r=sy.symbols('t_r d_r', real=True)                                                                                                         
        helmholtz_i_r_expression=sy.log(d_r)+((self.ideal_helmholtz_terms.e[0]*((t_r)**(1-4)))+(self.ideal_helmholtz_terms.e[1]*((t_r)**(2-4)))+(self.ideal_helmholtz_terms.e[2]*((t_r)**(3-4)))+(self.ideal_helmholtz_terms.e[3])+(self.ideal_helmholtz_terms.e[4]*((t_r)**(5-4))))+(self.ideal_helmholtz_terms.e[5]*(t_r**1.5))+(self.ideal_helmholtz_terms.e[6]*sy.log(t_r))+(self.ideal_helmholtz_terms.e[7]*sy.log(1-sy.exp(-self.ideal_helmholtz_terms.e[10]*t_r)))+(self.ideal_helmholtz_terms.e[8]*sy.log(1-sy.exp(-self.ideal_helmholtz_terms.e[11]*t_r)))+(self.ideal_helmholtz_terms.e[9]*sy.log((2/3)+sy.exp(self.ideal_helmholtz_terms.e[12]*t_r)))
        helmholtz_i_r_numerical=sy.lambdify((t_r,d_r),helmholtz_i_r_expression)
        return models.HelmholtzFunctions(reduced_ideal_exp_helmholtz   =   helmholtz_i_r_expression,
                                         reduced_ideal_num_helmholtz   =   helmholtz_i_r_numerical)
    
    @functools.cache
    def _reduced_real_helmholtzenergy_(self):
        helmholtz_r_r_expression=0
        t_r,d_r=sy.symbols('t_r d_r', real=True) 
        for index,term in enumerate(self.real_helmholtz_terms):
            if index<=9:
                helmholtz_r_r_expression=helmholtz_r_r_expression+(term.n*(d_r**term.i)*(t_r**term.j))
            elif 10<=index<=18:
                helmholtz_r_r_expression=helmholtz_r_r_expression+(term.n*(d_r**term.i)*(t_r**term.j)*(sy.exp(-d_r**term.l)))
         
        helmholtz_r_r_numerical=sy.lambdify((t_r,d_r),helmholtz_r_r_expression)
        return models.HelmholtzFunctions(reduced_real_exp_helmholtz    =   helmholtz_r_r_expression,
                                         reduced_real_num_helmholtz  =   helmholtz_r_r_numerical)
            
    