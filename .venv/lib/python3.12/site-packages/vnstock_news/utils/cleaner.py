_H='html.parser'
_G='multiple_newlines'
_F='multiple_spaces'
_E='html_tags'
_D=False
_C=' '
_B=True
_A=None
import re,unicodedata
from typing import List,Dict,Optional,Any,Union
import html
from bs4 import BeautifulSoup,Comment
from vnstock_news.utils.logger import setup_logger
class ContentCleaner:
	def __init__(A,debug:bool=_D):C="'";B='"';A.logger=setup_logger(A.__class__.__name__,debug);A.patterns={'email':'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b','phone':'\\b(\\+?[0-9]{1,3}[-.\\s]?)?(\\([0-9]{1,4}\\)|[0-9]{1,4})[-.\\s]?[0-9]{1,4}[-.\\s]?[0-9]{1,9}\\b','url':'https?://[^\\s]+',_E:'<[^>]*>',_F:'\\s+',_G:'\\n{3,}','special_chars':'[^\\w\\s\\.,;:!?\\(\\)\\[\\]\\{\\}\\-\\\'\\"\\/]','copyright':'©.*?\\d{4}','advertisement':'(advert(isement)?s?|sponsored content|promoted by)','social_media':'(follow us on|twitter|facebook|instagram|linkedin|subscribe)'};A.replacements={'&amp;':'&','&lt;':'<','&gt;':'>','&quot;':B,'&apos;':C,'\xa0':_C,'‘':C,'’':C,'“':B,'”':B,'–':'-','—':'--','…':'...'};A.compiled_patterns={A:re.compile(B,re.IGNORECASE)for(A,B)in A.patterns.items()}
	def clean_html(Q,html_content:str,remove_tags:List[str]=_A,keep_tags:List[str]=_A,remove_attrs:List[str]=_A,keep_attrs:List[str]=_A,remove_classes:List[str]=_A,remove_ids:List[str]=_A)->str:
		M='style';L=remove_ids;K=remove_classes;J=keep_attrs;I=keep_tags;H=html_content;F=remove_attrs;E=remove_tags
		if not H:return''
		if E is _A:E=['script',M,'iframe','noscript','meta','link','button','form','input','textarea','select','option']
		if F is _A:F=['onclick','onload','onerror','onmouseover','onmouseout',M,'data-','aria-']
		B=BeautifulSoup(H,_H)
		for N in B.find_all(text=lambda text:isinstance(text,Comment)):N.extract()
		if E:
			for A in E:
				for D in B.find_all(A):D.extract()
		if I:
			for A in B.find_all():
				if A.name not in I:A.extract()
		if K:
			for O in K:
				for D in B.find_all(class_=O):D.extract()
		if L:
			for P in L:
				for D in B.find_all(id=P):D.extract()
		for A in B.find_all():
			if F:
				for C in list(A.attrs.keys()):
					for G in F:
						if G.endswith('-')and C.startswith(G[:-1]):del A[C]
						elif C==G:del A[C]
			if J:
				for C in list(A.attrs.keys()):
					if C not in J:del A[C]
		return str(B)
	def clean_text(B,text:str,remove_urls:bool=_B,remove_emails:bool=_B,remove_phones:bool=_B,normalize_whitespace:bool=_B,normalize_unicode:bool=_B,convert_html_entities:bool=_B,remove_html_tags:bool=_B,limit_newlines:bool=_B)->str:
		if not text:return''
		A=text
		if convert_html_entities:A=html.unescape(A)
		if normalize_unicode:
			for(C,D)in B.replacements.items():A=A.replace(C,D)
			A=unicodedata.normalize('NFKC',A)
		if remove_urls:A=B.compiled_patterns['url'].sub(_C,A)
		if remove_emails:A=B.compiled_patterns['email'].sub(_C,A)
		if remove_phones:A=B.compiled_patterns['phone'].sub(_C,A)
		if remove_html_tags:A=B.compiled_patterns[_E].sub(_C,A)
		if normalize_whitespace:A=B.compiled_patterns[_F].sub(_C,A)
		if limit_newlines:A=B.compiled_patterns[_G].sub('\n\n',A)
		return A.strip()
	def extract_main_content(M,html_content:str,content_selectors:List[Dict[str,str]]=_A)->str:
		L='post-content';K='article-content';J='content';H=content_selectors;G=html_content;E='tag';C='id';B='class'
		if not G:return''
		F=BeautifulSoup(G,_H)
		if H is _A:H=[{E:'article'},{B:J},{B:K},{B:L},{B:'entry-content'},{C:J},{C:'main-content'},{C:K},{C:L}]
		for A in H:
			D=_A
			if E in A and B in A:D=F.find(A[E],class_=A[B])
			elif E in A and C in A:D=F.find(A[E],id=A[C])
			elif E in A:D=F.find(A[E])
			elif B in A:D=F.find(class_=A[B])
			elif C in A:D=F.find(id=A[C])
			if D:return str(D)
		I=F.find('body')
		if I:return str(I)
		return G
	def remove_boilerplate(E,text:str,boilerplate_phrases:List[str]=_A,remove_author_line:bool=_B,remove_publication_info:bool=_B)->str:
		B=boilerplate_phrases
		if not text:return''
		A=text
		if B is _A:B=['Share this article','Follow us on','Read more:','Click here to','Sign up for our newsletter','Related articles:','Source:','Credit:','Image credit:','Photo credit:','For more information','All rights reserved','Copyright ©']
		for C in B:D=re.compile(f"{re.escape(C)}.*?(\\n|$)",re.IGNORECASE);A=D.sub('\n',A)
		if remove_author_line:A=re.sub('^By\\s+[A-Z][a-z]+(\\s+[A-Z][a-z]+)*\\s*\\n','',A);A=re.sub('\\n[Bb]y\\s+[A-Z][a-z]+(\\s+[A-Z][a-z]+)*\\s*$','',A)
		if remove_publication_info:A=re.sub('^(Published|Updated|Posted)(\\s+on)?\\s+\\w+,\\s+\\w+\\s+\\d{1,2},\\s+\\d{4}.*?\\n','',A);A=re.sub('\\n(Published|Updated|Posted)(\\s+on)?\\s+\\w+,\\s+\\w+\\s+\\d{1,2},\\s+\\d{4}.*?$','',A)
		return A.strip()
	def normalize_title(D,title:str)->str:
		A=title
		if not A:return''
		A=html.unescape(A);A=re.sub('<[^>]+>','',A);A=re.sub('\\s+',_C,A).strip();B=['\\[sponsored\\]','\\[exclusive\\]','\\[update\\]','\\[video\\]','\\[photos\\]','\\[opinion\\]','\\|.*$','-\\s*\\w+\\.\\w+$']
		for C in B:A=re.sub(C,'',A,flags=re.IGNORECASE)
		if A:A=A[0].upper()+A[1:]
		return A.strip()
	def clean_article(B,article:Dict[str,Any])->Dict[str,Any]:
		I=article;H='html_content';G='markdown_content';F='short_description';E='title';D='author';C='publish_time'
		if not I:return{}
		A=I.copy()
		if E in A:A[E]=B.normalize_title(A[E])
		if F in A:A[F]=B.clean_text(A[F])
		if G in A:J=B.remove_boilerplate(A[G]);A[G]=B.clean_text(J,remove_urls=_D,remove_html_tags=_D)
		if H in A:K=B.extract_main_content(A[H]);A[H]=B.clean_html(K)
		if C in A and A[C]:A[C]=str(A[C])
		if D in A and A[D]:A[D]=B.clean_text(A[D])
		return A
	def clean_articles_batch(A,articles:List[Dict[str,Any]])->List[Dict[str,Any]]:return[A.clean_article(B)for B in articles]