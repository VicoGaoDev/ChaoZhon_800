-- 影响范围：
-- 1) 新增 prompt_optimize_styles 表，管理提示词优化系统风格；
-- 2) 新增 prompt_optimize_tasks 表，专门存放提示词优化记录（含 style_id / style_name_snapshot）；
-- 3) 兼容式回填旧 prompt_history.mode='promptOptimize' 数据到新表；
-- 4) 插入默认“通用优化”风格，保证上线后用户端可直接使用；
-- 5) 不删除旧数据，避免 SQL 执行后、代码发布前影响旧历史查询。
--
-- 回滚思路：
-- 1) 若仅执行了本脚本且尚未发布依赖代码，可删除 prompt_optimize_tasks / prompt_optimize_styles 表；
-- 2) 本脚本不会修改或删除 prompt_history 原始数据。

CREATE TABLE IF NOT EXISTS prompt_optimize_styles (
  id INT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  description VARCHAR(255) NOT NULL DEFAULT '',
  style_prompt TEXT NOT NULL,
  sort_order INT NOT NULL DEFAULT 100,
  status VARCHAR(20) NOT NULL DEFAULT 'enabled',
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  is_deleted TINYINT(1) NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_prompt_optimize_styles_sort (sort_order, id),
  KEY idx_prompt_optimize_styles_status_default (status, is_default, is_deleted)
);

CREATE TABLE IF NOT EXISTS prompt_optimize_tasks (
  id INT PRIMARY KEY AUTO_INCREMENT,
  user_id INT NOT NULL,
  legacy_prompt_history_id INT NULL,
  style_id INT NULL,
  style_name_snapshot VARCHAR(100) NOT NULL DEFAULT '',
  source VARCHAR(20) NOT NULL DEFAULT 'web',
  original_prompt VARCHAR(5000) NOT NULL DEFAULT '',
  optimized_prompt VARCHAR(5000) NOT NULL DEFAULT '',
  reference_images_json TEXT NOT NULL,
  source_image VARCHAR(500) NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'success',
  credit_cost INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_prompt_optimize_tasks_legacy_history (legacy_prompt_history_id),
  KEY idx_prompt_optimize_tasks_user_created (user_id, created_at),
  KEY idx_prompt_optimize_tasks_source_status_created (source, status, created_at),
  KEY idx_prompt_optimize_tasks_style_id (style_id),
  CONSTRAINT fk_prompt_optimize_tasks_user FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO prompt_optimize_styles (
  name,
  description,
  style_prompt,
  sort_order,
  status,
  is_default,
  is_deleted
)
SELECT
  '通用优化',
  '默认风格，适合通用中文生图提示词补全',
  '在保留用户原始意图前提下，补全构图、镜头、光线、色彩、材质、氛围和画面细节，输出适合直接生图的中文提示词。',
  10,
  'enabled',
  1,
  0
WHERE NOT EXISTS (
  SELECT 1
  FROM prompt_optimize_styles
  WHERE name = '通用优化'
    AND is_deleted = 0
);

INSERT INTO prompt_optimize_tasks (
  user_id,
  legacy_prompt_history_id,
  source,
  original_prompt,
  optimized_prompt,
  reference_images_json,
  source_image,
  status,
  credit_cost,
  created_at
)
SELECT
  ph.user_id,
  ph.id,
  'web',
  '',
  ph.prompt,
  CASE
    WHEN COALESCE(ph.source_image, '') <> '' THEN JSON_ARRAY(ph.source_image)
    ELSE JSON_ARRAY()
  END,
  COALESCE(ph.source_image, ''),
  'success',
  0,
  ph.created_at
FROM prompt_history ph
LEFT JOIN prompt_optimize_tasks pot
  ON pot.legacy_prompt_history_id = ph.id
WHERE ph.mode = 'promptOptimize'
  AND pot.id IS NULL;
