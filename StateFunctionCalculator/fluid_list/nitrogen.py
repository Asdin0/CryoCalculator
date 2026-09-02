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

class Nitrogen(GeneralClass.RealFluid):
    def __init__(self):
        constants=models.FluidConstants(molar_mass_kg_mol=0.02801348,
                    critical_temperature_K=126.192,
                    critical_pressure_Pa=3397800,
                    critical_density_kg_m3=313.3,
                    triplepoint_temperature_K=63.151,
                    triplepoint_pressure_Pa=12523,
                    reference_temperature_K=126.192,
                    reference_density_kg_m3=313.3,
                    acentric_factor=0.03724)
        
        saturation_terms=models.SaturationTerms(d_p_p=(-6.12445284,1.26327220,-0.765910082,-1.77570564),
                                                d_p_d=(-1.70127164,-3.70402649,1.29859383,-0.561424977,-2.68505381),
                                                b_p_d=(1.48654237,-0.280476066,0.0894143085,-0.119879866))
        
        ideal_helmholtz_terms=models.IdealHelmholtzTerms(e=(2.5,-12.76952708,-0.00784163,-0.0001934819,-0.00001247742,0.00000006678326,1.012941,26.65788))
        
        real_helmholtz_terms=((models.RealHelmholtzTerms(n=0.9248035752750000,i=1,j=0.250,l=0)),
                                 (models.RealHelmholtzTerms(n=-0.4924484894280000,i=1,j=0.875,l=0)),
                                 (models.RealHelmholtzTerms(n=0.661883336938,i=2,j=0.5,l=0)),
                                 (models.RealHelmholtzTerms(n=-1.92902649201,i=2,j=0.875,l=0)),
                                 (models.RealHelmholtzTerms(n=-0.0622469309629,i=3,j=0.375,l=0)),
                                 (models.RealHelmholtzTerms(n=0.349943957581,i=3,j=0.750,l=0)),
                                 (models.RealHelmholtzTerms(n=0.564857472498,i=1,j=0.5,l=1)),
                                 (models.RealHelmholtzTerms(n=-1.61720005987,i=1,j=0.750,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.481395031883,i=1,j=2,l=1)),
                                 (models.RealHelmholtzTerms(n=0.421150636384,i=3,j=1.250,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.0161962230825,i=3,j=3.5,l=1)),
                                 (models.RealHelmholtzTerms(n=0.172100994165,i=4,j=1,l=1)),
                                 (models.RealHelmholtzTerms(n=0.00735448924933,i=6,j=0.5,l=1)),
                                 (models.RealHelmholtzTerms(n=0.0168077305479,i=6,j=3,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.00107626664179,i=7,j=0,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.0137318088513,i=7,j=2.750,l=1)),
                                 (models.RealHelmholtzTerms(n=0.000635466899859,i=8,j=0.750,l=1)),
                                 (models.RealHelmholtzTerms(n=0.00304432279419,i=8,j=2.5,l=1)),
                                 (models.RealHelmholtzTerms(n=-0.0435762336045,i=1,j=4,l=2)),
                                 (models.RealHelmholtzTerms(n=-0.0723174889316,i=2,j=6,l=2)),
                                 (models.RealHelmholtzTerms(n=0.0389644315272,i=3,j=6,l=2)),
                                 (models.RealHelmholtzTerms(n=-0.021220136391,i=4,j=3,l=2)),
                                 (models.RealHelmholtzTerms(n=0.00408822981509,i=5,j=3,l=2)),
                                 (models.RealHelmholtzTerms(n=-0.0000551990017984,i=8,j=6,l=2)),
                                 (models.RealHelmholtzTerms(n=-0.0462016716479,i=4,j=16,l=3)),
                                 (models.RealHelmholtzTerms(n=-0.00300311716011,i=5,j=11,l=3)),
                                 (models.RealHelmholtzTerms(n=0.0368826891208,i=5,j=15,l=3)),
                                 (models.RealHelmholtzTerms(n=-0.0025585684622,i=8,j=12,l=3)),
                                 (models.RealHelmholtzTerms(n=0.00896915264558,i=3,j=12,l=4)),
                                 (models.RealHelmholtzTerms(n=-0.0044151337035,i=5,j=7,l=4)),
                                 (models.RealHelmholtzTerms(n=0.00133722924858,i=6,j=4,l=4)),
                                 (models.RealHelmholtzTerms(n=0.000264832491957,i=9,j=16,l=4)),
                                 (models.RealHelmholtzTerms(n=19.6688194015,i=1,j=0,l=2,o=20,k=325,y=1.16)),
                                 (models.RealHelmholtzTerms(n=-20.911560073,i=1,j=1,l=2,o=20,k=325,y=1.16)),
                                 (models.RealHelmholtzTerms(n=0.0167788306989,i=3,j=2,l=2,o=15,k=300,y=1.13)),
                                 (models.RealHelmholtzTerms(n=2627.67566274,i=2,j=3,l=2,o=25,k=275,y=1.25)))
        
        acceptable_parameters=models.AcceptableParameters(T_maximum_value_K=1000,T_minimum_value_K=65,P_maximum_value_Pa=2200000000,P_minimum_value_Pa=1)
        super().__init__(constants, saturation_terms, ideal_helmholtz_terms, real_helmholtz_terms, acceptable_parameters)

    def dewpoint_pressure(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            dewpoint_pressure=((mth.exp((self.constants.reference_temperature_K/t)*((self.saturation_terms.d_p_p[0]*teta)+(self.saturation_terms.d_p_p[1]*(teta)**1.5)+(self.saturation_terms.d_p_p[2]*(teta)**2.5)+(self.saturation_terms.d_p_p[3]*(teta)**5)))*self.constants.critical_pressure_Pa))
        else:
            dewpoint_pressure=None
        return dewpoint_pressure

    def dewpoint_density(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            dewpoint_density=((mth.exp((self.constants.reference_temperature_K/t)*((self.saturation_terms.d_p_d[0]*(teta**0.34))+(self.saturation_terms.d_p_d[1]*(teta**(5/6)))+(self.saturation_terms.d_p_d[2]*(teta**(7/6)))+(self.saturation_terms.d_p_d[3]*(teta**(13/6)))+(self.saturation_terms.d_p_d[4]*(teta**(14/3)))))*self.constants.reference_density_kg_m3))  
        else:
            dewpoint_density=None
        return dewpoint_density
    
    def bubblepoint_pressure(self, t):
        bubblepoint_pressure=self.dewpoint_pressure(t)
        return bubblepoint_pressure

    def bubblepoint_density(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            teta=1-(t/self.constants.reference_temperature_K)
            bubblepoint_density=((mth.exp((self.saturation_terms.b_p_d[0]*(teta**0.3294))+(self.saturation_terms.b_p_d[1]*(teta**(2/3)))+(self.saturation_terms.b_p_d[2]*(teta**(8/3)))+(self.saturation_terms.b_p_d[3]*(teta**(35/6))))*self.constants.reference_density_kg_m3))
        else:
            bubblepoint_density=None
        return bubblepoint_density
    
    def meltingpoint_pressure(self,t):
        self._check_input_(t)
        if t<=self.constants.critical_temperature_K:
            meltingpoint_pressure=((12798.1*(((t/self.constants.triplepoint_temperature_K)**(1.78963))-1))*self.constants.triplepoint_pressure_Pa)+1
        else:
            meltingpoint_pressure=None
        return meltingpoint_pressure
    
    @functools.cache
    def _reduced_ideal_helmholtzenergy_(self):
        t_r,d_r=sy.symbols('t_r d_r', real=True)                                                                                                         
        helmholtz_i_r_expression=((sy.log(d_r))+(self.ideal_helmholtz_terms.e[0]*sy.log(t_r))+(self.ideal_helmholtz_terms.e[1])+(self.ideal_helmholtz_terms.e[2]*t_r)+(self.ideal_helmholtz_terms.e[3]/t_r)+(self.ideal_helmholtz_terms.e[4]/(t_r)**2)+(self.ideal_helmholtz_terms.e[5]/(t_r)**3)+(self.ideal_helmholtz_terms.e[6]*sy.log(1-sy.exp(-1*self.ideal_helmholtz_terms.e[7]*t_r))))                                                                                            
        helmholtz_i_r_numerical=sy.lambdify((t_r,d_r),helmholtz_i_r_expression)
        return models.HelmholtzFunctions(reduced_ideal_exp_helmholtz   =   helmholtz_i_r_expression,
                                         reduced_ideal_num_helmholtz   =   helmholtz_i_r_numerical)
    
    @functools.cache
    def _reduced_real_helmholtzenergy_(self):
        helmholtz_r_r_expression=0
        t_r,d_r=sy.symbols('t_r d_r', real=True) 
        for index,term in enumerate(self.real_helmholtz_terms):
            if index<=5:
                helmholtz_r_r_expression=helmholtz_r_r_expression+(term.n*(d_r**term.i)*(t_r**term.j))
            elif 6<=index<=31:
                helmholtz_r_r_expression=helmholtz_r_r_expression+(term.n*(d_r**term.i)*(t_r**term.j)*(sy.exp(-d_r**term.l)))
            elif 32<=index<=35:
                helmholtz_r_r_expression=helmholtz_r_r_expression+(term.n*(d_r**term.i)*(t_r**term.j))*sy.exp(-term.o*((d_r-1)**2)-term.k*((t_r-term.y)**2))
        
        helmholtz_r_r_numerical=sy.lambdify((t_r,d_r),helmholtz_r_r_expression)
        return models.HelmholtzFunctions(reduced_real_exp_helmholtz    =   helmholtz_r_r_expression,
                                         reduced_real_num_helmholtz  =   helmholtz_r_r_numerical)

