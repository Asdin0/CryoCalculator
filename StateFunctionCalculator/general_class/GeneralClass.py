import models
from abc import ABC, abstractmethod
import math as mth
import sympy as sy
import pandas as pd
import matplotlib.pyplot as plt
import functools
import typing


class RealFluid(ABC):
    def __init__(self,
                 constants,
                 saturation_terms,
                 ideal_helmholtz_terms,
                 real_helmholtz_terms,
                 acceptable_parameters):
        self.constants=constants
        self.saturation_terms=saturation_terms
        self.ideal_helmholtz_terms=ideal_helmholtz_terms
        self.real_helmholtz_terms=real_helmholtz_terms
        self.acceptable_parameters=acceptable_parameters

    def _check_input_(self,t:typing.Optional[float]=None,p:typing.Optional[float]=None):
        if t!=None:
            if t<self.acceptable_parameters.T_minimum_value_K or t>self.acceptable_parameters.T_maximum_value_K:
                raise ValueError(f"The temperature must be between {self.acceptable_parameters.T_minimum_value_K }[k] and {self.acceptable_parameters.T_maximum_value_K }[[K]")
        if p!=None:
            if p<0 or p>self.acceptable_parameters.P_maximum_value_Pa:
                raise ValueError(f"The pressure must be between 0[Pa] and {self.acceptable_parameters.P_maximum_value_Pa }[[Pa]")
    
    def phases(self,t:float, p:float = None, density:float = None):
        phase=None
        if p is None and density is None:
            return phase
        bubblepoint_pressure = self.bubblepoint_pressure(t)
        dewpoint_pressure = self.dewpoint_pressure(t)
        bubblepoint_density = self.bubblepoint_density(t)
        dewpoint_density = self.dewpoint_density(t)
        meltingpoint_pressure = self.meltingpoint_pressure(t)

        if p is not None:    
            if t>self.constants.critical_temperature_K and p<=self.constants.critical_pressure_Pa: 
                phase_p="gas"
            
            elif t>self.constants.critical_temperature_K and p>self.constants.critical_pressure_Pa: 
                phase_p="supercritical"
            
            elif t<=self.constants.critical_temperature_K and p<bubblepoint_pressure and p>dewpoint_pressure:
                phase_p="two-phase"
            
            elif t<=self.constants.critical_temperature_K and p>=bubblepoint_pressure and p<meltingpoint_pressure:
                phase_p="liquid"

            elif t<=self.constants.critical_temperature_K and p<=dewpoint_pressure:
                phase_p="vapor"

            elif t<=self.constants.critical_temperature_K and p>=meltingpoint_pressure:
                phase_p="solid"

        if density is not None:
            if t>self.constants.critical_temperature_K and density<=self.constants.critical_density_kg_m3: 
                phase_d="gas"
            
            elif t>self.constants.critical_temperature_K and density>self.constants.critical_density_kg_m3: 
                phase_d="supercritical"
            
            elif t<=self.constants.critical_temperature_K and density<bubblepoint_density and density>dewpoint_density:
                phase_d="two-phase"
            
            elif t<=self.constants.critical_temperature_K and density>=bubblepoint_density:
                phase_d="liquid"
    
            elif t<=self.constants.critical_temperature_K and density<=dewpoint_density:
                phase_d="vapor"


        if p is not None and density is not None and phase_p!="solid":
            return phase_p if phase_p==phase_d else phase
        elif p is not None and density is None:
            return phase_p
        elif p is None and density is not None:
            return phase_d

    def _acentric_factor_(self):
        if self.dewpoint_pressure(Tr)==self.bubblepoint_pressure(Tr):
            Tr=0.7*self.constants.critical_temperature_K
            saturation_pressure=self.dewpoint_pressure(Tr)
            acentric_factor=-mth.log10(saturation_pressure/self.constants.critical_pressure_Pa)-1
            return acentric_factor
        else:
            raise ValueError("It is not possible to calculate the eccentricity factor because the fluid is not pure")
    
    def _aproximate_density_(self,t:float,p:float):
        self.check_input(t,p)
        aproximate_density=(p*self.constants.molar_mass_kg_mol)/(self.constants.universal_gas_constant_J_mol_K*t)
        return aproximate_density
    
    def _bisection_algorithm_(self,t:float,p:typing.Optional[float]=None,density:typing.Optional[float]=None):
        ideal_helmholtz_results=self._reduced_ideal_helmholtzenergy_()
        helmholtz_i_r_expression=ideal_helmholtz_results.reduced_ideal_exp_helmholtz
        helmholtz_i_r_numerical=ideal_helmholtz_results.reduced_ideal_num_helmholtz

        real_helmholtz_results=self._reduced_real_helmholtzenergy_()
        helmholtz_r_r_expression=real_helmholtz_results.reduced_real_exp_helmholtz
        helmholtz_r_r_numerical=real_helmholtz_results.reduced_real_num_helmholtz

        partial_derivative_results=self._partial_derivatives_(helmholtz_i_r_expression=helmholtz_i_r_expression,
                                                            helmholtz_r_r_expression=helmholtz_r_r_expression)
        devpar_helmholtz_tao_i_r_numerical=partial_derivative_results.redtemp_pdev_redtemp_red_ideal_num_helmholtz
        devpar_tao_helmholtz_r_r_numerical=partial_derivative_results.redtemp_pdev_redtemp_red_real_num_helmholtz
        devpar_delta_helmholtz_r_r_numerical=partial_derivative_results.reddens_pdev_reddens_red_real_num_helmholtz

        if density!=None:
            real_density=density
        elif density==None:

            p_tolerance=1
            d_tolerance=0.00001

            if t<=self.constants.critical_temperature_K:
                if abs(p-self.dewpoint_pressure(t))<p_tolerance or abs(p-self.bubblepoint_pressure(t))<p_tolerance or self.dewpoint_pressure(t)<=p<=self.bubblepoint_pressure(t):
                    raise ValueError(f"At temperature {t} and pressure {p} the fluid is in a two-phase condition")
                elif p<self.dewpoint_pressure(t):
                    a=10**-10*self.constants.critical_density_kg_m3
                    b=self.dewpoint_density(t)*1.05
                elif p>=self.dewpoint_pressure(t):
                    a=self.bubblepoint_density(t)*0.95
                    b=4*self.constants.critical_density_kg_m3
            elif t>self.constants.critical_temperature_K:
                a=10**-10*self.constants.critical_density_kg_m3
                b=4*self.constants.critical_density_kg_m3

            pressure_function_a=self._pressure_function_(t=t,p=p,real_density=a,delta_devpar_delta_helmholtz_r_r=self._dinamic_pardev_helmholz_(t=t,real_density=a,devpar_delta_helmholtz_r_r_numerical=devpar_delta_helmholtz_r_r_numerical))
            pressure_function_b=self._pressure_function_(t=t,p=p,real_density=b,delta_devpar_delta_helmholtz_r_r=self._dinamic_pardev_helmholz_(t=t,real_density=b,devpar_delta_helmholtz_r_r_numerical=devpar_delta_helmholtz_r_r_numerical))
            

            if pressure_function_a*pressure_function_b>=0:

                if abs(pressure_function_a)<=d_tolerance:
                    real_density=a
                    
                elif abs(pressure_function_b)<=d_tolerance:
                    real_density=b
                    
                else:
                    raise ValueError(f"The interval [{pressure_function_a},{pressure_function_b}] does not obey the intermediate value theorem.")     
            else:  
                iterator=0
                while abs(pressure_function_a-pressure_function_b)>d_tolerance:
                    c=(a+b)/2
                    pressure_function_c=self._pressure_function_(t=t,p=p,real_density=c,delta_devpar_delta_helmholtz_r_r=self._dinamic_pardev_helmholz_(t=t,real_density=c,devpar_delta_helmholtz_r_r_numerical=devpar_delta_helmholtz_r_r_numerical))

                    if iterator>1000:
                        raise ValueError("the maximum number of iterations of the bisection algorithm has been reached")
                    
                    elif abs(pressure_function_c)<=d_tolerance:
                        real_density=c
                        break
                    elif pressure_function_a*pressure_function_c<0:
                        b=c
                        pressure_function_b=pressure_function_c

                    elif pressure_function_b*pressure_function_c<0:
                        a=c
                        pressure_function_a=pressure_function_c
                    real_density=(a+b)/2
                    iterator+=1

        reduced_temperature=self.constants.reference_temperature_K/t
        reduced_density=real_density/self.constants.reference_density_kg_m3
        
        helmholtz_i_r=helmholtz_i_r_numerical(reduced_temperature,reduced_density)
        helmholtz_r_r=helmholtz_r_r_numerical(reduced_temperature,reduced_density)

        delta_devpar_delta_helmholtz_r_r=reduced_density*devpar_delta_helmholtz_r_r_numerical(reduced_temperature,reduced_density)
        tao_devpar_tao_helmholtz_r_r=reduced_temperature*devpar_tao_helmholtz_r_r_numerical(reduced_temperature,reduced_density)
        tao_devpar_helmholtz_tao_i_r=reduced_temperature*devpar_helmholtz_tao_i_r_numerical(reduced_temperature,reduced_density) 

        return models.HelmholtzFunctions(reduced_ideal_helmholtz=helmholtz_i_r,reduced_real_helmholtz=helmholtz_r_r,redtemp_pdev_redtemp_red_ideal_helmholtz=tao_devpar_helmholtz_tao_i_r,redtemp_pdev_redtemp_red_real_helmholtz=tao_devpar_tao_helmholtz_r_r,reddens_pdev_reddens_red_real_helmholtz=delta_devpar_delta_helmholtz_r_r)

    def _state_function_(self,t:float,p:typing.Optional[float]=None,density:typing.Optional[float]=None):
        search_algorithms_results=self._bisection_algorithm_(t=t,p=p,density=density)
        helmholtz_i_r=search_algorithms_results.reduced_ideal_helmholtz
        helmholtz_r_r=search_algorithms_results.reduced_real_helmholtz
        tao_devpar_helmholtz_tao_i_r=search_algorithms_results.redtemp_pdev_redtemp_red_ideal_helmholtz
        tao_devpar_tao_helmholtz_r_r=search_algorithms_results.redtemp_pdev_redtemp_red_real_helmholtz
        delta_devpar_delta_helmholtz_r_r=search_algorithms_results.reddens_pdev_reddens_red_real_helmholtz
        
        compressibility_factor=1+delta_devpar_delta_helmholtz_r_r
        if density==None:
            real_density=(p*self.constants.molar_mass_kg_mol)/(compressibility_factor*self.constants.universal_gas_constant_J_mol_K*t)
        else:
            real_density=density
        specifica_internal_energy=float(((tao_devpar_helmholtz_tao_i_r+tao_devpar_tao_helmholtz_r_r)*self.constants.universal_gas_constant_J_mol_K*t)/self.constants.molar_mass_kg_mol)
        specific_enthalpy=float((((tao_devpar_helmholtz_tao_i_r+tao_devpar_tao_helmholtz_r_r+delta_devpar_delta_helmholtz_r_r+1)*self.constants.universal_gas_constant_J_mol_K*t)/self.constants.molar_mass_kg_mol))
        specific_entropy=float(((tao_devpar_helmholtz_tao_i_r+tao_devpar_tao_helmholtz_r_r-helmholtz_i_r-helmholtz_r_r)*self.constants.universal_gas_constant_J_mol_K)/self.constants.molar_mass_kg_mol)
        
        return models.StateFunctions(density_kg_m3=real_density,compressibility_factor=compressibility_factor,internal_energy_J_kg=specifica_internal_energy,enthalpy_J_kg=specific_enthalpy,entropy_J_kg_K=specific_entropy)

    def _dinamic_pardev_helmholz_(self,t:float,real_density:float,devpar_delta_helmholtz_r_r_numerical:float):
        self._check_input_(t)
        reduced_temperature=self.constants.reference_temperature_K/t
        reduced_density=real_density/self.constants.reference_density_kg_m3 

        delta_devpar_delta_helmholtz_r_r=reduced_density*devpar_delta_helmholtz_r_r_numerical(reduced_temperature,reduced_density)
        return delta_devpar_delta_helmholtz_r_r
    
    def _pressure_function_(self,t:float,p:float,real_density:float,delta_devpar_delta_helmholtz_r_r:float):
        self._check_input_(t,p)
        calculated_p=float((real_density/self.constants.molar_mass_kg_mol)*self.constants.universal_gas_constant_J_mol_K*t*(1+delta_devpar_delta_helmholtz_r_r))
        p_function=calculated_p-p
        return(p_function)

    @functools.cache
    def _partial_derivatives_(self,helmholtz_i_r_expression,helmholtz_r_r_expression):
        t_r,d_r=sy.symbols('t_r d_r', real=True)  
        devpar_helmholtz_tao_i_r_symbol=sy.diff(helmholtz_i_r_expression,t_r)                                                                              
        devpar_helmholtz_tao_i_r_numerical=sy.lambdify((t_r,d_r),devpar_helmholtz_tao_i_r_symbol)                                                                  

        devpar_delta_helmholtz_r_r_symbol=sy.diff(helmholtz_r_r_expression,d_r)                                                                            
        devpar_delta_helmholtz_r_r_numerical=sy.lambdify((t_r,d_r),devpar_delta_helmholtz_r_r_symbol)                                                            

        devpar_tao_helmholtz_r_r_symbol=sy.diff(helmholtz_r_r_expression,t_r)
        devpar_tao_helmholtz_r_r_numerical=sy.lambdify((t_r,d_r),devpar_tao_helmholtz_r_r_symbol)
        
        return models.HelmholtzFunctions(redtemp_pdev_redtemp_red_ideal_exp_helmholtz  =   devpar_helmholtz_tao_i_r_symbol,
                                redtemp_pdev_redtemp_red_ideal_num_helmholtz  =   devpar_helmholtz_tao_i_r_numerical,
                                redtemp_pdev_redtemp_red_real_exp_helmholtz   =   devpar_tao_helmholtz_r_r_symbol,
                                redtemp_pdev_redtemp_red_real_num_helmholtz   =   devpar_tao_helmholtz_r_r_numerical,
                                reddens_pdev_reddens_red_real_exp_helmholtz   =   devpar_delta_helmholtz_r_r_symbol,
                                reddens_pdev_reddens_red_real_num_helmholtz   =   devpar_delta_helmholtz_r_r_numerical)
    
    def calculated_functions(self,t:float,p:typing.Optional[float]=None,density:typing.Optional[float]=None):
        state_function_results=self._state_function_(t=t,p=p,density=density)
        
        phase=self.phases(t,p,density)
        
        dew_point_density_kg_m3=self.dewpoint_density(t)
        dew_point_pressure_Pa=self.dewpoint_pressure(t)
        bubble_point_density_kg_m3=self.bubblepoint_density(t)
        bubble_point_pressure_Pa=self.bubblepoint_pressure(t)
        melting_point_pressure_Pa=self.meltingpoint_pressure(t)
        
        density=state_function_results.density_kg_m3
        compressibility_factor=state_function_results.compressibility_factor
        internal_energy=state_function_results.internal_energy_J_kg
        enthalpy=state_function_results.enthalpy_J_kg
        entropy=state_function_results.entropy_J_kg_K

        return models.OutputFunctions(temperature_input_K=t,
                            pressure_input_Pa=p,
                            phase=phase,
                            density_kg_m3=density,
                            compressibility_factor=compressibility_factor, 
                            internal_energy_J_kg=internal_energy,
                            enthalpy_J_kg=enthalpy,
                            entropy_J_kg_K=entropy,
                            dew_point_density_kg_m3=dew_point_density_kg_m3,
                            dew_point_pressure_Pa=dew_point_pressure_Pa,
                            bubble_point_density_kg_m3=bubble_point_density_kg_m3,
                            bubble_point_pressure_Pa=bubble_point_pressure_Pa,
                            melting_point_pressure_Pa=melting_point_pressure_Pa)
    
    def value_table(self,t:float,p:float):
        approximate=4
        values_temperature=[]
        values_pressure=[]
        values_phase=[]
        values_density=[]
        values_compressibility_factor=[]
        values_internal_energy=[]
        values_enthalpy=[]
        values_entropy=[]
        values_dew_point_pressure=[]
        values_dew_point_density=[]
        values_bubble_point_pressure=[]
        values_bubble_point_density=[]

        resultant_data=self.calculated_functions(t,p)

        values_temperature.append(resultant_data.temperature_input_K)
        values_pressure.append(resultant_data.pressure_input_Pa)
        values_phase.append(resultant_data.phase)
        values_density.append(f"{resultant_data.density_kg_m3:.{approximate}f}")
        values_compressibility_factor.append(f"{resultant_data.compressibility_factor:.{approximate}f}")
        values_internal_energy.append(f"{resultant_data.internal_energy_J_kg:.{approximate}f}")
        values_enthalpy.append(f"{resultant_data.enthalpy_J_kg:.{approximate}f}")
        values_entropy.append(f"{resultant_data.entropy_J_kg_K:.{approximate}f}")
        values_dew_point_pressure.append(resultant_data.dew_point_pressure_Pa)
        values_dew_point_density.append(resultant_data.dew_point_density_kg_m3)
        values_bubble_point_pressure.append(resultant_data.bubble_point_pressure_Pa)
        values_bubble_point_density.append(resultant_data.bubble_point_density_kg_m3)

        table_data={"Temperature[K]":values_temperature,
                "Pressure[Pa]":values_pressure,
                "Phase":values_phase,
                "Density[kg/m3]":values_density,
                "Compressibility_factor":values_compressibility_factor,
                "Internal energy[J/kg]":values_internal_energy,
                "Enthalpy[J/kg]":values_enthalpy,
                "Entropy_J_kg_K[J/(kg*K)]":values_entropy,
                "Dew_point_pressure_Pa":values_dew_point_pressure,
                "Dew_point_density_kg_m3":values_dew_point_density,
                "Bubble_point_pressure_Pa":values_bubble_point_pressure,
                "Bubble_point_density_kg_m3":values_bubble_point_density}
    
        output_table=pd.DataFrame(table_data).set_index('Temperature[K]')
        return output_table
    
    def isothermal_table(self,t:float,p_min:float,p_max:float,p_variation:float):
        approximate=4
        values_temperature=[]
        values_pressure=[]
        values_density=[]
        values_compressibility_factor=[]
        values_internal_energy=[]
        values_enthalpy=[]
        values_entropy=[]
        values_dew_point_pressure=[]
        values_dew_point_density=[]
        values_bubble_point_pressure=[]
        values_bubble_point_density=[]

        for i in range(int((p_max-p_min)/p_variation)):
            resultant_data=self.calculated_functions(t,p_min)

            values_temperature.append(resultant_data.temperature_input_K)
            values_pressure.append(resultant_data.pressure_input_Pa)
            values_density.append(f"{resultant_data.density_kg_m3:.{approximate}f}")
            values_compressibility_factor.append(f"{resultant_data.compressibility_factor:.{approximate}f}")
            values_internal_energy.append(f"{resultant_data.internal_energy_J_kg:.{approximate}f}")
            values_enthalpy.append(f"{resultant_data.enthalpy_J_kg:.{approximate}f}")
            values_entropy.append(f"{resultant_data.entropy_J_kg_K:.{approximate}f}")
            values_dew_point_pressure.append(resultant_data.dew_point_pressure_Pa)
            values_dew_point_density.append(resultant_data.dew_point_density_kg_m3)
            values_bubble_point_pressure.append(resultant_data.bubble_point_pressure_Pa)
            values_bubble_point_density.append(resultant_data.bubble_point_density_kg_m3)
            p_min=p_min+p_variation

        table_data={"Temperature[K]":values_temperature,
                        "Pressure[Pa]":values_pressure,
                        "Density[kg/m3]":values_density,
                        "Compressibility_factor":values_compressibility_factor,
                        "Internal energy[J/kg]":values_internal_energy,
                        "Enthalpy[J/kg]":values_enthalpy,
                        "Entropy_J_kg_K[J/(kg*K)]":values_entropy,
                        "Dew_point_pressure_Pa":values_dew_point_pressure,
                        "Dew_point_density_kg_m3":values_dew_point_density,
                        "Bubble_point_pressure_Pa":values_bubble_point_pressure,
                        "Bubble_point_density_kg_m3":values_bubble_point_density}

        output_table=pd.DataFrame(table_data).set_index('Temperature[K]')
        output_table.head(int((p_max-p_min)/p_variation))
        return output_table

    def isobaric_table(self,p:float,t_min:float,t_max:float,t_variation:float):
        approximate=4
        values_temperature=[]
        values_pressure=[]
        values_density=[]
        values_compressibility_factor=[]
        values_internal_energy=[]
        values_enthalpy=[]
        values_entropy=[]
        values_dew_point_pressure=[]
        values_dew_point_density=[]
        values_bubble_point_pressure=[]
        values_bubble_point_density=[]

        for i in range(int((t_max-t_min)/t_variation)):
            resultant_data=self.calculated_functions(t_min,p)

            values_temperature.append(resultant_data.temperature_input_K)
            values_pressure.append(resultant_data.pressure_input_Pa)
            values_density.append(f"{resultant_data.density_kg_m3:.{approximate}f}")
            values_compressibility_factor.append(f"{resultant_data.compressibility_factor:.{approximate}f}")
            values_internal_energy.append(f"{resultant_data.internal_energy_J_kg:.{approximate}f}")
            values_enthalpy.append(f"{resultant_data.enthalpy_J_kg:.{approximate}f}")
            values_entropy.append(f"{resultant_data.entropy_J_kg_K:.{approximate}f}")
            values_dew_point_pressure.append(resultant_data.dew_point_pressure_Pa)
            values_dew_point_density.append(resultant_data.dew_point_density_kg_m3)
            values_bubble_point_pressure.append(resultant_data.bubble_point_pressure_Pa)
            values_bubble_point_density.append(resultant_data.bubble_point_density_kg_m3)

            t_min=t_min+t_variation

        table_data={"Temperature[K]":values_temperature,
                        "Pressure[Pa]":values_pressure,
                        "Density[kg/m3]":values_density,
                        "Compressibility_factor":values_compressibility_factor,
                        "Internal energy[J/kg]":values_internal_energy,
                        "Enthalpy[J/kg]":values_enthalpy,
                        "Entropy_J_kg_K[J/(kg*K)]":values_entropy,
                        "Dew_point_pressure_Pa":values_dew_point_pressure,
                        "Dew_point_density_kg_m3":values_dew_point_density,
                        "Bubble_point_pressure_Pa":values_bubble_point_pressure,
                        "Bubble_point_density_kg_m3":values_bubble_point_density}
        output_table=pd.DataFrame(table_data).set_index('Temperature[K]')
        output_table.head(int((t_max-t_min)/t_variation))
        return output_table

    def h_p_diagram(self):
        t_min=self.acceptable_parameters.T_minimum_value_K
        t_max=self.constants.critical_temperature_K
        t_variation=0.1

        values_pressure=[]
        values_enthalpy=[]

        for i in range(int((t_max-t_min)/t_variation)):
            dew_point_density_kg_m3=self.dewpoint_density(t_min)
            dew_point_pressure_Pa=self.dewpoint_pressure(t_min)
            bubble_point_density_kg_m3=self.bubblepoint_density(t_min)
            bubble_point_pressure_Pa=self.bubblepoint_pressure(t_min)

            enthalpy_J_kg_vaporphase=self.calculated_functions(t=t_min,density=dew_point_density_kg_m3).enthalpy_J_kg
            enthalpy_J_kg_liquidphase=self.calculated_functions(t=t_min,density=bubble_point_density_kg_m3).enthalpy_J_kg
            

            values_pressure.append(mth.log(dew_point_pressure_Pa))
            values_enthalpy.append(enthalpy_J_kg_vaporphase)
            values_pressure.append(mth.log(bubble_point_pressure_Pa))
            values_enthalpy.append(enthalpy_J_kg_liquidphase)

            t_min=t_min+t_variation

        table_data={"Enthalpy[J/kg]":values_enthalpy,
                    "Logarithmic pressure[Pa]":values_pressure}

        output_table=pd.DataFrame(table_data)
        output_table.head(int((t_max-t_min)/t_variation))
        
        plt.style.use('seaborn-v0_8')
        plt.title("Enthalpy-Pressure Diagram")
        plt.xlabel("h [J/kg]")
        plt.ylabel("ln(P) [Pa]")

        plt.scatter(output_table["Enthalpy[J/kg]"],output_table["Logarithmic pressure[Pa]"])
        plt.show()
        return output_table
    
    def t_s_diagram(self):
        t_min=self.acceptable_parameters.T_minimum_value_K
        t_max=self.constants.critical_temperature_K
        t_variation=0.1
        
        values_temperature=[]
        values_entropy=[]

        for i in range(int((t_max-t_min)/t_variation)):
            dew_point_density_kg_m3=self.dewpoint_density(t_min)
            bubble_point_density_kg_m3=self.bubblepoint_density(t_min)

            entropy_J_kg_K_vaporphase=self.calculated_functions(t=t_min,density=dew_point_density_kg_m3).entropy_J_kg_K
            entropy_J_kg_K_liquidphase=self.calculated_functions(t=t_min,density=bubble_point_density_kg_m3).entropy_J_kg_K

            values_temperature.append(t_min)
            values_entropy.append(entropy_J_kg_K_vaporphase)
            values_temperature.append(t_min)
            values_entropy.append(entropy_J_kg_K_liquidphase)

            t_min=t_min+t_variation

        table_data={"Entropy[J/kg*K]":values_entropy,
                    "Temperature[K]":values_temperature}

        output_table=pd.DataFrame(table_data)
        output_table.head(int((t_max-t_min)/t_variation))
        plt.style.use('seaborn-v0_8')
        plt.title("Temperature-Entropy Diagram")
        plt.xlabel("t [K]")
        plt.ylabel("s [kJ/kg*K]")

        plt.scatter(output_table["Entropy[J/kg*K]"],output_table["Temperature[K]"])

        plt.show()
        return output_table
    
    
    def p_d_diagram(self):
        t_min=self.acceptable_parameters.T_minimum_value_K
        t_max=self.constants.critical_temperature_K
        t_variation=0.1

        values_pressure=[mth.log(self.constants.critical_pressure_Pa)]
        values_density=[self.constants.critical_density_kg_m3]

        for i in range(int((t_max-t_min)/t_variation)):
            dew_point_density_kg_m3=self.dewpoint_density(t_min)
            dew_point_pressure_Pa=self.dewpoint_pressure(t_min)
            bubble_point_density_kg_m3=self.bubblepoint_density(t_min)

            values_pressure.append(mth.log(dew_point_pressure_Pa))
            values_density.append(dew_point_density_kg_m3)
            values_pressure.append(mth.log(dew_point_pressure_Pa))
            values_density.append(bubble_point_density_kg_m3)

            t_min=t_min+t_variation

        table_data={"Density[kg/m3]":values_density,
                    "Pressure[Pa]":values_pressure}

        output_table=pd.DataFrame(table_data)
        output_table.head(int((t_max-t_min)/t_variation))
        plt.style.use('seaborn-v0_8')
        plt.title("Pressure-Density Diagram")
        plt.xlabel("p [Pa]")
        plt.ylabel("d [kg/m3]")

        plt.scatter(output_table["Density[kg/m3]"],output_table["Pressure[Pa]"])
        plt.show()
        return output_table

    
    @abstractmethod
    def dewpoint_pressure(self,t:float):
        pass
      
    @abstractmethod
    def dewpoint_density(self,t:float):
        pass
    
    @abstractmethod
    def bubblepoint_pressure(self,t:float):
        pass

    @abstractmethod
    def bubblepoint_density(self,t:float):
        pass
    
    @abstractmethod
    def meltingpoint_pressure(self,t:float):
        pass

    @abstractmethod
    def _reduced_ideal_helmholtzenergy_(self):
        pass

    @abstractmethod
    def _reduced_real_helmholtzenergy_(self):
        pass
    





