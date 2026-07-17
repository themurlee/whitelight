[2026-07-17T19:48:02.769498Z] [INFO] Fetching data for SPY from 2026-04-08 to 2026-07-17...
[2026-07-17T19:48:02.885458Z] [WARNING] API attempt 1 failed: {"message":"subscription does not permit querying recent SIP data"}

[2026-07-17T19:48:05.002598Z] [WARNING] API attempt 2 failed: {"message":"subscription does not permit querying recent SIP data"}

[2026-07-17T19:48:07.094029Z] [WARNING] API attempt 3 failed: {"message":"subscription does not permit querying recent SIP data"}

[2026-07-17T19:48:07.094444Z] [ERROR] Failed to fetch data for SPY after 3 retries.
[2026-07-17T19:48:59.827254Z] [INFO] Fetching data for SPY from 2026-04-08 to 2026-07-17...
[2026-07-17T19:49:00.007176Z] [INFO] Data ingestion complete for SPY. Saved 69 daily files.
[2026-07-17T19:56:33.571311Z] [WARNING] SELL signal received for SPY, but no open position exists. Skipping liquidation.
[2026-07-17T19:56:43.339773Z] [INFO] Risk Check Passed: Allocating 6 shares of SPY (Value: $4463.22 <= Max allocation: $5000.00)
[2026-07-17T19:56:43.374852Z] [INFO] BUY Order Submitted successfully: ID=5b7b73f3-4692-40fd-b7f6-924f09dd2803, Qty=6, Status=OrderStatus.PENDING_NEW
[2026-07-17T19:56:46.377706Z] [INFO] Risk Check Passed: Allocating 6 shares of SPY (Value: $4463.22 <= Max allocation: $4999.99)
[2026-07-17T19:56:46.413543Z] [INFO] BUY Order Submitted successfully: ID=9903ad15-e9ef-483a-bbd1-84fbda13347b, Qty=6, Status=OrderStatus.PENDING_NEW
[2026-07-17T19:56:58.233562Z] [INFO] Risk Check Passed: Allocating 6 shares of SPY (Value: $4463.22 <= Max allocation: $5000.00)
[2026-07-17T19:56:58.377519Z] [INFO] BUY Order Submitted successfully: ID=e2d9ad13-a680-4823-8ca5-d47a74d1fe4e, Qty=6, Status=OrderStatus.PENDING_NEW
[2026-07-17T20:00:31.868997Z] [INFO] Risk Check Passed: Allocating 6 shares of SPY (Value: $4463.22 <= Max allocation: $4998.46)
[2026-07-17T20:00:31.898855Z] [INFO] BUY Order Submitted successfully: ID=35b90b83-76eb-442e-8327-e0917c6caff9, Qty=6, Status=OrderStatus.ACCEPTED
[2026-07-17T20:03:45.322672Z] [WARNING] BUY signal received for SPY, but open order already exists (Count: 1). Skipping purchase.
[2026-07-17T20:03:50.042166Z] [INFO] Risk Check: Liquidating position of 18 shares of SPY.
[2026-07-17T20:03:50.070151Z] [ERROR] Execution failed: {"code":40310000,"existing_order_id":"35b90b83-76eb-442e-8327-e0917c6caff9","message":"potential wash trade detected. use complex orders","reject_reason":"opposite side market/stop order exists"}
[2026-07-17T20:04:04.526722Z] [INFO] Cancelling 1 existing open orders for SPY before executing new action...
[2026-07-17T20:04:06.125533Z] [INFO] Risk Check: Liquidating position of 18 shares of SPY.
[2026-07-17T20:04:06.221743Z] [INFO] SELL Order Submitted successfully: ID=98404df7-47bc-4085-bf55-ed15ff714f19, Qty=18, Status=OrderStatus.ACCEPTED
