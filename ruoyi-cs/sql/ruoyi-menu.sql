-- 拷进正式若依时用。本仓库 ruoyi-cs 是可独立运行的业务模块，菜单 ID 避开常见内置段。
INSERT INTO sys_menu VALUES (2100, '智能客服', 0, 20, 'cs', NULL, '', '', 1, 0, 'M', '0', '0', '', 'message', 'admin', sysdate(), '', NULL, '知识库客服后台');
INSERT INTO sys_menu VALUES (2101, '知识库', 2100, 1, 'document', 'cs/document/index', '', '', 1, 0, 'C', '0', '0', 'kb:document:list', 'documentation', 'admin', sysdate(), '', NULL, '');
INSERT INTO sys_menu VALUES (2102, '会话记录', 2100, 2, 'session', 'cs/session/index', '', '', 1, 0, 'C', '0', '0', 'cs:session:list', 'log', 'admin', sysdate(), '', NULL, '');
INSERT INTO sys_menu VALUES (2103, '人工工单', 2100, 3, 'ticket', 'cs/ticket/index', '', '', 1, 0, 'C', '0', '0', 'cs:ticket:list', 'list', 'admin', sysdate(), '', NULL, '');
