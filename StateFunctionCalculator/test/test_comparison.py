import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
path_to_A = os.path.join(project_root, 'fluid_list')
sys.path.insert(0, path_to_A)

import nitrogen
from CoolProp.CoolProp import PropsSI
import pytest


def input_dataset(t_start:float,t_max:float,t_variation:float,p_min:float,p_max:float,p_variation:float):
    input_data=[]
    t_min=t_start
    for p in range(int((p_max-p_min)/p_variation)):
        for t in range(int((t_max-t_min)/t_variation)):
            input_data.append((t_min,p_min))
            t_min=t_min+t_variation
        if (t_max-t_min)<=1:
            t_min=t_start
        p_min=p_min+p_variation
    return input_data

fluid_test=nitrogen.Nitrogen()
t_start_value=fluid_test.acceptable_parameters.T_minimum_value_K
t_max_value=fluid_test.acceptable_parameters.T_maximum_value_K
t_variation_value=1
p_min_value=1
p_max_value=2000000000
p_variation_value=10000000

input_data=input_dataset(t_start=t_start_value,t_max=t_max_value,t_variation=t_variation_value,p_min=p_min_value,p_max=p_max_value,p_variation=p_variation_value)



T_K_reference=273.15
P_Pa_reference=100000
output_program_reference=fluid_test.calculated_functions(T_K_reference,P_Pa_reference)


@pytest.mark.parametrize(["T_K","P_Pa"],input_data)
def test_density(T_K,P_Pa):       
    output_program=fluid_test.calculated_functions(T_K,P_Pa)
    coolprop_output=PropsSI('D','T',T_K,'P',P_Pa,'Nitrogen')-PropsSI('D','T',T_K_reference,'P',P_Pa_reference,'Nitrogen')
    assert output_program.density_kg_m3-output_program_reference.density_kg_m3==pytest.approx(coolprop_output,rel=0.1)

@pytest.mark.parametrize(["T_K","P_Pa"],input_data)
def test_enthalpy(T_K,P_Pa):       
    output_program=fluid_test.calculated_functions(T_K,P_Pa)
    coolprop_output=PropsSI('H','T',T_K,'P',P_Pa,'Nitrogen')-PropsSI('H','T',T_K_reference,'P',P_Pa_reference,'Nitrogen')
    assert output_program.enthalpy_J_kg-output_program_reference.enthalpy_J_kg==pytest.approx(coolprop_output,rel=0.1)

@pytest.mark.parametrize(["T_K","P_Pa"],input_data)
def test_entropy(T_K,P_Pa):       
    output_program=fluid_test.calculated_functions(T_K,P_Pa)
    coolprop_output=PropsSI('S','T',T_K,'P',P_Pa,'Nitrogen')-PropsSI('S','T',T_K_reference,'P',P_Pa_reference,'Nitrogen')
    assert output_program.entropy_J_kg_K-output_program_reference.entropy_J_kg_K==pytest.approx(coolprop_output,rel=0.1)

