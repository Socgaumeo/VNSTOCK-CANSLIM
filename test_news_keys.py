from vnstock_news import EnhancedNewsCrawler
import asyncio

def main():
    from vnstock import Vnstock
    stock = Vnstock().stock(symbol='FRT', source='VCI')
    # Try quote.news() or similar. 
    # I will guess 'news' is under 'quote' or 'company'
    try:
        news = stock.company.news()
        print(news)
        if news is not None and not news.empty:
            print(news.columns.tolist())
            print(news.iloc[0].to_dict())
    except Exception as e:
        print(e)

if __name__ == "__main__":
    main()
