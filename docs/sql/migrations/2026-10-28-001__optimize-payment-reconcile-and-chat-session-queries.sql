-- 影响范围：
-- 1) 支付补偿扫描：匹配 payment_orders 按 created_at/id 分页扫描、status/reconcile_until_at 过滤的查询；
-- 2) 支付订单后台列表：匹配按 created_at/id 或 status+created_at/id 排序分页；
-- 3) AI 对话会话列表：匹配按 user_id/is_deleted/last_message_at/id 排序分页。
--
-- 回滚思路：按索引名 DROP INDEX。

SET @index_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'payment_orders' AND INDEX_NAME = 'idx_payment_orders_created_id'
);
SET @ddl := IF(@index_exists = 0, 'CREATE INDEX idx_payment_orders_created_id ON payment_orders (created_at, id)', 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @index_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'payment_orders' AND INDEX_NAME = 'idx_payment_orders_status_created_id'
);
SET @ddl := IF(@index_exists = 0, 'CREATE INDEX idx_payment_orders_status_created_id ON payment_orders (status, created_at, id)', 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @index_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'payment_orders' AND INDEX_NAME = 'idx_payment_orders_reconcile_scan'
);
SET @ddl := IF(@index_exists = 0, 'CREATE INDEX idx_payment_orders_reconcile_scan ON payment_orders (created_at, id, status, reconcile_until_at, order_no)', 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @index_exists := (
  SELECT COUNT(*) FROM information_schema.STATISTICS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'chat_sessions' AND INDEX_NAME = 'idx_chat_sessions_user_last_message_id'
);
SET @ddl := IF(@index_exists = 0, 'CREATE INDEX idx_chat_sessions_user_last_message_id ON chat_sessions (user_id, is_deleted, last_message_at, id)', 'SELECT 1');
PREPARE stmt FROM @ddl; EXECUTE stmt; DEALLOCATE PREPARE stmt;
