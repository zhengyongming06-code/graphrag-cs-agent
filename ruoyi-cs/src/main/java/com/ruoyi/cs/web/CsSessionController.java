package com.ruoyi.cs.web;

import com.ruoyi.cs.common.AjaxResult;
import com.ruoyi.cs.common.TableDataInfo;
import com.ruoyi.cs.python.PythonAiClient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/cs/session")
@PreAuthorize("hasAnyRole('ADMIN','CS')")
public class CsSessionController {
    private final JdbcTemplate jdbc;
    private final PythonAiClient python;

    public CsSessionController(JdbcTemplate jdbc, PythonAiClient python) {
        this.jdbc = jdbc;
        this.python = python;
    }

    @GetMapping("/list")
    public TableDataInfo list() {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT session_id, turn_count, created_at, updated_at, sync_time FROM cs_session ORDER BY updated_at DESC"
        );
        return new TableDataInfo(rows, rows.size());
    }

    @GetMapping("/{sessionId}")
    public AjaxResult get(@PathVariable String sessionId) {
        syncOne(sessionId);
        Map<String, Object> head = jdbc.queryForMap(
                "SELECT session_id, turn_count, created_at, updated_at, sync_time FROM cs_session WHERE session_id=?",
                sessionId
        );
        List<Map<String, Object>> turns = jdbc.queryForList(
                "SELECT role, content, intent, confidence, created_at FROM cs_turn WHERE session_id=? ORDER BY id",
                sessionId
        );
        head.put("turns", turns);
        return AjaxResult.success(head);
    }

    @PostMapping("/sync")
    public AjaxResult sync() {
        List<Map<String, Object>> remote = python.listSessions(100);
        int n = 0;
        if (remote != null) {
            for (Map<String, Object> row : remote) {
                upsertSummary(row);
                n++;
            }
        }
        return AjaxResult.success("已同步 " + n + " 条会话摘要", Map.of("count", n));
    }

    private void syncOne(String sessionId) {
        Map<String, Object> detail = python.getSession(sessionId);
        upsertSummary(detail);
        jdbc.update("DELETE FROM cs_turn WHERE session_id=?", sessionId);
        @SuppressWarnings("unchecked")
        List<Map<String, Object>> turns = (List<Map<String, Object>>) detail.get("turns");
        if (turns == null) {
            return;
        }
        for (Map<String, Object> t : turns) {
            jdbc.update(
                    "INSERT INTO cs_turn (session_id, role, content, intent, confidence, created_at) VALUES (?,?,?,?,?,?)",
                    sessionId,
                    String.valueOf(t.getOrDefault("role", "")),
                    String.valueOf(t.getOrDefault("content", "")),
                    String.valueOf(t.getOrDefault("intent", "")),
                    t.get("confidence") instanceof Number n ? n.doubleValue() : 0.0,
                    t.get("created_at")
            );
        }
    }

    private void upsertSummary(Map<String, Object> row) {
        Object sid = row.get("session_id");
        if (sid == null) {
            return;
        }
        jdbc.update(
                """
                MERGE INTO cs_session (session_id, turn_count, created_at, updated_at, sync_time)
                KEY (session_id)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                String.valueOf(sid),
                row.get("turn_count") instanceof Number n ? n.intValue() : 0,
                row.get("created_at"),
                row.get("updated_at")
        );
    }
}
