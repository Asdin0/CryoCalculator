import math as mth
import pandas as pd
import typing

class EqHeatExchanger():
    def logarithmic_mean_temperature_difference(in_t_h:typing.Optional[float]=None,out_t_h:typing.Optional[float]=None,in_t_c:typing.Optional[float]=None,out_t_c:typing.Optional[float]=None):
        if in_t_h and out_t_h and in_t_c and out_t_c !=None:
            return ((in_t_h-in_t_c)-(out_t_h-out_t_c))/(mth.log((in_t_h-in_t_c)/(out_t_h-out_t_c)))
    def epsilon(in_t_h:typing.Optional[float]=None,out_t_h:typing.Optional[float]=None,in_t_c:typing.Optional[float]=None,out_t_c:typing.Optional[float]=None,m_h:typing.Optional[float]=None,m_c:typing.Optional[float]=None,cp_h:typing.Optional[float]=None,cp_c:typing.Optional[float]=None):
        if (m_h and m_c and cp_h and cp_c and in_t_h and in_t_c)!=None and (out_t_h or out_t_c)!=None:
            c_h=m_h*cp_h
            c_c=m_c*cp_c
            c_min=min(c_h,c_c)
            qmax=c_min*(in_t_h-in_t_c)
            if out_t_h!=None:
                q=c_h*(in_t_h-out_t_h)
            elif out_t_c!=None:
                q=c_c*(out_t_c-in_t_c)
            epsilon=q/qmax
        else:
            epsilon=None
        return epsilon
    
    def ntu(epsilon:typing.Optional[float]=None,m_h:typing.Optional[float]=None,m_c:typing.Optional[float]=None,cp_h:typing.Optional[float]=None,cp_c:typing.Optional[float]=None):
        if (epsilon and m_h and m_c and cp_h and cp_c)!=None:
            c_h=m_h*cp_h
            c_c=m_c*cp_c
            c_min=min(c_h,c_c)
            c_max=max(c_h,c_c)
            ntu=-(mth.log(1-epsilon*(1+(c_min/c_max))))/(1+(c_min/c_max))
        else:
            ntu=None
        return ntu
    
class CfHeatExchanger():
    def logarithmic_mean_temperature_difference(in_t_h:typing.Optional[float]=None,out_t_h:typing.Optional[float]=None,in_t_c:typing.Optional[float]=None,out_t_c:typing.Optional[float]=None):
        if in_t_h and out_t_h and in_t_c and out_t_c !=None:
            return ((in_t_h-out_t_c)-(out_t_h-in_t_c))/(mth.log((in_t_h-out_t_c)/(out_t_h-in_t_c)))
    
    def epsilon(in_t_h:typing.Optional[float]=None,out_t_h:typing.Optional[float]=None,in_t_c:typing.Optional[float]=None,out_t_c:typing.Optional[float]=None,m_h:typing.Optional[float]=None,m_c:typing.Optional[float]=None,cp_h:typing.Optional[float]=None,cp_c:typing.Optional[float]=None):
        if (m_h and m_c and cp_h and cp_c and in_t_h and in_t_c)!=None and (out_t_h or out_t_c)!=None:
            c_h=m_h*cp_h
            c_c=m_c*cp_c
            c_min=min(c_h,c_c)
            qmax=c_min*(in_t_h-in_t_c)
            if out_t_h!=None:
                q=c_h*(in_t_h-out_t_h)
            elif out_t_c!=None:
                q=c_c*(out_t_c-in_t_c)
            epsilon=q/qmax
        else:
            epsilon=None
        return epsilon
    
    def ntu(epsilon:typing.Optional[float]=None,m_h:typing.Optional[float]=None,m_c:typing.Optional[float]=None,cp_h:typing.Optional[float]=None,cp_c:typing.Optional[float]=None):
        if (epsilon and m_h and m_c and cp_h and cp_c)!=None:
            c_h=m_h*cp_h
            c_c=m_c*cp_c
            c_min=min(c_h,c_c)
            c_max=max(c_h,c_c)
            c=c_min/c_max
            ntu=(1/(c-1))*mth.log((epsilon-1)/(epsilon*c-1))
        else:
            ntu=None
        return ntu
        



