-- Image canvas for 800AI: projects, nodes, edges, groups, example canvases.
-- Run once before deploying /api/canvases. Depends only on users and tasks.
-- Does not create video task columns.

CREATE TABLE user_canvas (
  id INT AUTO_INCREMENT PRIMARY KEY,
  project_id VARCHAR(16) NOT NULL,
  user_id INT NOT NULL,
  source_example_id INT NULL,
  name VARCHAR(100) NOT NULL DEFAULT '',
  viewport_x DOUBLE NOT NULL DEFAULT 0,
  viewport_y DOUBLE NOT NULL DEFAULT 0,
  zoom DOUBLE NOT NULL DEFAULT 0.5,
  is_deleted BOOLEAN NOT NULL DEFAULT 0,
  deleted_at DATETIME NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY idx_user_canvas_project_id (project_id),
  INDEX idx_user_canvas_user_id (user_id),
  INDEX idx_user_canvas_user_updated_at (user_id, updated_at),
  INDEX idx_user_canvas_user_deleted_updated (user_id, is_deleted, updated_at),
  INDEX idx_user_canvas_source_example_id (source_example_id),
  INDEX idx_user_canvas_updated_id (updated_at, id),
  CONSTRAINT fk_user_canvas_user FOREIGN KEY (user_id) REFERENCES users(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

ALTER TABLE tasks
  ADD COLUMN canvas_id INT NULL,
  ADD COLUMN is_example_template_seed BOOLEAN NOT NULL DEFAULT 0 AFTER used_fallback_api;

CREATE INDEX idx_tasks_canvas_id ON tasks (canvas_id);
CREATE INDEX idx_tasks_user_canvas_deleted_created ON tasks (user_id, canvas_id, is_deleted, created_at);

ALTER TABLE tasks
  ADD CONSTRAINT fk_tasks_canvas
  FOREIGN KEY (canvas_id) REFERENCES user_canvas(id)
  ON DELETE SET NULL;

CREATE TABLE canvas_groups (
  id INT AUTO_INCREMENT PRIMARY KEY,
  canvas_id INT NOT NULL,
  name VARCHAR(100) NOT NULL DEFAULT '',
  color VARCHAR(32) NOT NULL DEFAULT '#ffab27',
  x DOUBLE NOT NULL DEFAULT 0,
  y DOUBLE NOT NULL DEFAULT 0,
  width DOUBLE NOT NULL DEFAULT 320,
  height DOUBLE NOT NULL DEFAULT 220,
  z_index INT NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_canvas_groups_canvas_id (canvas_id),
  INDEX idx_canvas_groups_canvas_z (canvas_id, z_index),
  CONSTRAINT fk_canvas_groups_canvas FOREIGN KEY (canvas_id) REFERENCES user_canvas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE canvas_nodes (
  id INT AUTO_INCREMENT PRIMARY KEY,
  canvas_id INT NOT NULL,
  group_id INT NULL,
  task_id INT NULL,
  node_type VARCHAR(20) NOT NULL DEFAULT 'task',
  content VARCHAR(5000) NOT NULL DEFAULT '',
  image_url VARCHAR(1000) NOT NULL DEFAULT '',
  x DOUBLE NOT NULL DEFAULT 0,
  y DOUBLE NOT NULL DEFAULT 0,
  width DOUBLE NOT NULL DEFAULT 320,
  height DOUBLE NOT NULL DEFAULT 420,
  z_index INT NOT NULL DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_canvas_nodes_canvas_id (canvas_id),
  INDEX idx_canvas_nodes_canvas_z (canvas_id, z_index),
  INDEX idx_canvas_nodes_group_id (group_id),
  INDEX idx_canvas_nodes_task_id (task_id),
  INDEX idx_canvas_nodes_canvas_updated_id (canvas_id, updated_at, id),
  CONSTRAINT fk_canvas_nodes_canvas FOREIGN KEY (canvas_id) REFERENCES user_canvas(id),
  CONSTRAINT fk_canvas_nodes_group FOREIGN KEY (group_id) REFERENCES canvas_groups(id) ON DELETE SET NULL,
  CONSTRAINT fk_canvas_nodes_task FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE canvas_edges (
  id INT AUTO_INCREMENT PRIMARY KEY,
  canvas_id INT NOT NULL,
  source_node_id INT NOT NULL,
  target_node_id INT NOT NULL,
  edge_type VARCHAR(20) NOT NULL DEFAULT 'reference',
  source_anchor VARCHAR(10) NOT NULL DEFAULT 'auto',
  target_anchor VARCHAR(10) NOT NULL DEFAULT 'auto',
  is_collapsed BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_canvas_edges_canvas_id (canvas_id),
  INDEX idx_canvas_edges_source_node_id (source_node_id),
  INDEX idx_canvas_edges_target_node_id (target_node_id),
  CONSTRAINT fk_canvas_edges_canvas FOREIGN KEY (canvas_id) REFERENCES user_canvas(id) ON DELETE CASCADE,
  CONSTRAINT fk_canvas_edges_source_node FOREIGN KEY (source_node_id) REFERENCES canvas_nodes(id) ON DELETE CASCADE,
  CONSTRAINT fk_canvas_edges_target_node FOREIGN KEY (target_node_id) REFERENCES canvas_nodes(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE example_canvas_projects (
  id INT NOT NULL AUTO_INCREMENT,
  source_canvas_id INT NOT NULL,
  source_project_id VARCHAR(16) NOT NULL,
  title VARCHAR(100) NOT NULL DEFAULT '',
  subtitle VARCHAR(255) NOT NULL DEFAULT '',
  cover_url VARCHAR(1000) NOT NULL DEFAULT '',
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  sort_order INT NOT NULL DEFAULT 0,
  preview_urls_json TEXT NOT NULL,
  snapshot_json TEXT NOT NULL,
  created_by INT NULL,
  updated_by INT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_example_canvas_projects_source_canvas_id (source_canvas_id),
  UNIQUE KEY uq_example_canvas_projects_source_project_id (source_project_id),
  INDEX idx_example_canvas_projects_status_sort (status, sort_order, id),
  INDEX idx_example_canvas_projects_created_by (created_by),
  INDEX idx_example_canvas_projects_updated_by (updated_by),
  CONSTRAINT fk_example_canvas_projects_source_canvas_id FOREIGN KEY (source_canvas_id) REFERENCES user_canvas (id),
  CONSTRAINT fk_example_canvas_projects_created_by FOREIGN KEY (created_by) REFERENCES users (id),
  CONSTRAINT fk_example_canvas_projects_updated_by FOREIGN KEY (updated_by) REFERENCES users (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

UPDATE tasks t
JOIN user_canvas c ON c.id = t.canvas_id
SET t.is_example_template_seed = 1
WHERE c.source_example_id IS NOT NULL
  AND COALESCE(t.credit_cost, 0) = 0
  AND t.enqueued_at IS NULL
  AND t.request_started_at IS NULL
  AND t.request_finished_at IS NULL;
