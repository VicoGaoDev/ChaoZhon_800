-- 影响范围：新增活动管理表，用于后台维护 AI 生图页活动弹窗与横幅。
-- 回滚思路：DROP TABLE activities;
-- 执行前置：代码发布前完成该迁移，确保活动管理接口可正常读写。

CREATE TABLE IF NOT EXISTS activities (
  id INTEGER NOT NULL AUTO_INCREMENT,
  business_id VARCHAR(32) NOT NULL,
  title VARCHAR(200) NOT NULL DEFAULT '',
  image_url VARCHAR(500) NOT NULL DEFAULT '',
  description TEXT NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'enabled',
  sort_order INTEGER NOT NULL DEFAULT 100,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_activities_business_id (business_id),
  INDEX ix_activities_status_sort (status, sort_order, id),
  INDEX ix_activities_created_at (created_at)
);
