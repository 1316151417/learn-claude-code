# https://akshare.akfamily.xyz/data/stock/stock.html#a
# https://gushitong.baidu.com/index/hk-HSI
# uv sync --index-url https://pypi.tuna.tsinghua.edu.cn/simple
# uv config set index-url https://pypi.tuna.tsinghua.edu.cn/simple

import akshare as ak

stock_sse_summary_df = ak.stock_sse_summary()
print(stock_sse_summary_df)