_C=', '
_B=True
_A=None
import re
from typing import List,Dict,Union,Optional,Any,Callable
import pandas as pd
from datetime import datetime
from urllib.parse import urlparse
from vnstock_news.utils.logger import setup_logger
class ValidationError(Exception):0
class InputValidator:
	def __init__(A,debug:bool=False):A.logger=setup_logger(A.__class__.__name__,debug)
	def validate_url(D,url:str,required:bool=_B)->str:
		A=url
		if not A and not required:return A
		if not A:raise ValidationError('URL is required.')
		A=A.strip()
		try:
			B=urlparse(A)
			if not all([B.scheme,B.netloc]):raise ValidationError(f"Invalid URL format: {A}")
			if B.scheme not in['http','https']:raise ValidationError(f"URL must use HTTP or HTTPS: {A}")
		except Exception as C:raise ValidationError(f"URL parsing error: {C}")
		return A
	def validate_urls(C,urls:Union[str,List[str]])->List[str]:
		A=urls
		if isinstance(A,str):A=[A]
		if not A:raise ValidationError('At least one URL is required.')
		B=[]
		for(D,E)in enumerate(A):
			try:B.append(C.validate_url(E))
			except ValidationError as F:raise ValidationError(f"URL at index {D} is invalid: {F}")
		return B
	def validate_site_name(D,site_name:str,SITES_CONFIG:List[str],required:bool=_B)->Optional[str]:
		C=required;B=SITES_CONFIG;A=site_name
		if not A and not C:return
		if not A and C:raise ValidationError('Site name is required.')
		A=A.strip().lower()
		if A not in B:raise ValidationError(f"Invalid site name: '{A}'. Supported sites: {_C.join(B)}")
		return A
	def validate_config(C,config:Dict,required_keys:List[str])->Dict:
		A=config
		if not A:raise ValidationError('Configuration dictionary is required.')
		if not isinstance(A,dict):raise ValidationError(f"Configuration must be a dictionary, not {type(A).__name__}.")
		B=[B for B in required_keys if B not in A]
		if B:raise ValidationError(f"Missing required configuration keys: {_C.join(B)}")
		return A
	def validate_time_frame(E,time_frame:str)->str:
		A=time_frame
		if not A:raise ValidationError('Time frame is required.')
		A=A.strip().lower();D='^(\\d+)([hdm])$';C=re.match(D,A)
		if not C:raise ValidationError(f"Invalid time frame format: '{A}'. Use format like '1h' for 1 hour, '2d' for 2 days, or '30m' for 30 minutes.")
		B,F=C.groups()
		try:
			B=int(B)
			if B<=0:raise ValidationError(f"Time frame value must be positive, got {B}.")
		except ValueError:raise ValidationError(f"Time frame value must be an integer, got '{B}'.")
		return A
	def validate_date(D,date_str:str,format_str:str='%Y-%m-%d')->datetime:
		B=format_str;A=date_str
		if not A:raise ValidationError('Date string is required.')
		A=A.strip()
		try:return datetime.strptime(A,B)
		except ValueError as C:raise ValidationError(f"Invalid date format: {C}. Expected format: {B}")
	def validate_positive_int(D,value:Any,param_name:str,required:bool=_B,default:Optional[int]=_A)->Optional[int]:
		B=param_name;A=value
		if A is _A:
			if required:raise ValidationError(f"{B} is required.")
			return default
		try:
			C=int(A)
			if C<=0:raise ValidationError(f"{B} must be positive, got {C}.")
			return C
		except ValueError:raise ValidationError(f"{B} must be an integer, got '{A}'.")
	def validate_dataframe(B,df:pd.DataFrame,required_columns:List[str])->pd.DataFrame:
		if df is _A or df.empty:raise ValidationError('DataFrame cannot be None or empty.')
		A=[A for A in required_columns if A not in df.columns]
		if A:raise ValidationError(f"Missing required columns: {_C.join(A)}")
		return df
	def validate_sort_order(B,sort_order:str)->str:
		A=sort_order
		if not A:raise ValidationError('Sort order is required.')
		A=A.lower().strip()
		if A not in['asc','desc']:raise ValidationError(f"Invalid sort order: '{A}'. Must be 'asc' or 'desc'.")
		return A
	def validate_choice(E,value:Any,choices:List[Any],param_name:str,required:bool=_B,default:Any=_A)->Any:
		C=param_name;B=choices;A=value
		if A is _A:
			if required:raise ValidationError(f"{C} is required.")
			return default
		if A not in B:D=_C.join([str(A)for A in B]);raise ValidationError(f"{C} must be one of: {D}, got '{A}'.")
		return A
	def validate(D,validation_dict:Dict[str,Dict[str,Any]])->Dict[str,Any]:
		E={};A=[]
		for(F,B)in validation_dict.items():
			G=B.pop('value');C=B.pop('validator')
			if not hasattr(D,C):A.append(f"Unknown validator: {C}");continue
			H=getattr(D,C)
			try:E[F]=H(G,**B)
			except ValidationError as I:A.append(f"{F}: {str(I)}")
		if A:raise ValidationError('\n'.join(A))
		return E