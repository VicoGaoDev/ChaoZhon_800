-- Add a bounded reconciliation window for newly created Alipay payment orders.
-- Historical orders keep NULL and will not be picked up by the scheduler.

ALTER TABLE payment_orders
  ADD COLUMN reconcile_until_at DATETIME NULL AFTER credited_at;

CREATE INDEX idx_payment_orders_reconcile_until
  ON payment_orders (reconcile_until_at, status);

CREATE TABLE payment_reconcile_scan_runs (
  id INT NOT NULL AUTO_INCREMENT,
  status VARCHAR(20) NOT NULL DEFAULT 'running',
  duration_seconds INT NOT NULL DEFAULT 60,
  scanned_count INT NOT NULL DEFAULT 0,
  paid_detected_count INT NOT NULL DEFAULT 0,
  credited_count INT NOT NULL DEFAULT 0,
  event_payload TEXT NULL,
  started_at DATETIME NOT NULL,
  active_until DATETIME NOT NULL,
  finished_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_payment_reconcile_scan_runs_status (status, active_until),
  INDEX idx_payment_reconcile_scan_runs_created_at (created_at)
);
