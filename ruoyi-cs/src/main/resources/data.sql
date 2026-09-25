MERGE INTO cs_user (username, password, nick_name, roles, status)
    KEY (username)
    VALUES ('admin', '{noop}admin123', '管理员', 'admin,kb,cs', '0');
MERGE INTO cs_user (username, password, nick_name, roles, status)
    KEY (username)
    VALUES ('kb', '{noop}kb123', '知识库管理员', 'kb', '0');
MERGE INTO cs_user (username, password, nick_name, roles, status)
    KEY (username)
    VALUES ('agent', '{noop}agent123', '坐席', 'cs', '0');
