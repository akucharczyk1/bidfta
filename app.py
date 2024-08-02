from flask import Flask, render_template, request
import requests
from datetime import datetime, timedelta
import http.client
import json
import pytz

app = Flask(__name__)


@app.template_filter('datetimeformat')
def datetimeformat(value):
    if value is None or not isinstance(value, str):
        return "Unknown Time"
    try:
        dt = datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ')
        est = pytz.timezone('US/Eastern')
        utc_dt = dt.replace(tzinfo=pytz.utc)
        local_dt = utc_dt.astimezone(est)
        return local_dt.strftime('%m/%d/%y - %I:%M %p')
    except ValueError:
        return "Invalid Date"


@app.template_filter('calculate_price_after_fees')
def calculate_price_after_fees(current_bid):
    try:
        if isinstance(current_bid, str):
            bid = float(current_bid.strip('$').replace(',', ''))
        else:
            bid = current_bid
        fee_percentage = 0.1725  # 17.25% premium
        freight_charge = 1.00  # $1 freight charge
        sales_tax_percentage = 0.08  # 8% sales tax

        price_with_premium = bid + (bid * fee_percentage) + freight_charge
        price_after_fees = price_with_premium + (price_with_premium * sales_tax_percentage)
        return f"${price_after_fees:.2f}"
    except ValueError:
        return "N/A"


def get_auction_items(auction_id, pages=6):
    items = []
    conn = http.client.HTTPSConnection("auction.bidfta.io")
    payload = ""
    headers = {
        'accept': "application/json, text/plain, */*",
        'accept-language': "en-US,en;q=0.9",
        'origin': "https://www.bidfta.com",
        'priority': "u=1, i",
        'referer': "https://www.bidfta.com/",
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        'sec-ch-ua-mobile': "?0",
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': "empty",
        'sec-fetch-mode': "cors",
        'sec-fetch-site': "cross-site",
        'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    for page in range(1, pages + 1):
        conn.request("GET", f"/api/item/getItemsByAuctionId/{auction_id}?pageId={page}&auctionId={auction_id}", payload,
                     headers)
        res = conn.getresponse()
        data = res.read()
        response = json.loads(data.decode("utf-8"))
        print(f"Response for page {page}: {response}")  # Debug print
        if isinstance(response, list):
            items.extend(response)
        else:
            print(f"Unexpected response format: {response}")

    return items


@app.route('/')
def home():
    url = "https://auction.bidfta.io/api/auction/getAuctions?pageId=1&categories=Categories%20-%20All&pastAuction=false&selectedLocationIds=616"
    headers = {
        'accept': "application/json, text/plain, */*",
        'accept-language': "en-US,en;q=0.9",
        'origin': "https://www.bidfta.com",
        'priority': "u=1, i",
        'referer': "https://www.bidfta.com/",
        'sec-ch-ua': '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        'sec-ch-ua-mobile': "?0",
        'sec-ch-ua-platform': '"macOS"',
        'sec-fetch-dest': "empty",
        'sec-fetch-mode': "cors",
        'sec-fetch-site': "cross-site",
        'user-agent': "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    auctions = response.json()

    return render_template('index.html', auctions=auctions)


@app.route('/auction/<int:auction_id>')
def auction_detail(auction_id):
    condition = request.args.get('condition', 'all')
    msrp_min = request.args.get('msrp_min', None)
    bidders_max = request.args.get('bidders_max', None)

    auction_items = get_auction_items(auction_id)
    auction_title = f"Auction {auction_id}"  # Default title, can be replaced with actual title if available
    if auction_items:
        auction_title = auction_items[0].get('auctionNumber', auction_title)

    # Apply filters
    filtered_items = []
    for item in auction_items:
        try:
            msrp_condition = float(item['msrp']) >= float(msrp_min) if msrp_min else True
            bidders_condition = int(item['bidsCount']) <= int(bidders_max) if bidders_max else True
            if (condition == 'all' or item['condition'] == condition) and msrp_condition and bidders_condition:
                filtered_items.append(item)
        except ValueError as e:
            print(f"Error filtering item: {e}")  # Debug print

    return render_template('auction.html', auction_details=filtered_items, auction_title=auction_title,
                           auction_id=auction_id)


@app.route('/auction/<int:auction_id>/ideal')
def ideal_buys(auction_id):
    auction_items = get_auction_items(auction_id)
    auction_title = f"Auction {auction_id}"  # Default title, can be replaced with actual title if available
    if auction_items:
        auction_title = auction_items[0].get('auctionNumber', auction_title)

    ideal_items = []
    for item in auction_items:
        try:
            price_after_fees = float(calculate_price_after_fees(item['currentBid']).strip('$').replace(',', ''))
            if price_after_fees < (float(item['msrp']) * 0.5) and int(item['bidsCount']) <= 4 and float(
                    item['msrp']) >= 50:
                ideal_items.append(item)
        except ValueError as e:
            print(f"Error filtering ideal buy: {e}")  # Debug print

    return render_template('auction.html', auction_details=ideal_items, auction_title=auction_title,
                           auction_id=auction_id)


if __name__ == '__main__':
    app.run(debug=True)
