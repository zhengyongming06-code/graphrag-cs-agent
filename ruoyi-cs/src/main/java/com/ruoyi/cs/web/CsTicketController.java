package com.ruoyi.cs.web;

import com.ruoyi.cs.common.AjaxResult;
import com.ruoyi.cs.common.ServiceException;
import com.ruoyi.cs.common.TableDataInfo;
import com.ruoyi.cs.python.PythonAiClient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/cs/ticket")
@PreAuthorize("hasAnyRole('ADMIN','CS')")
public class CsTicketController {
    private final JdbcTemplate jdbc;
    private final PythonAiClient python;

    public CsTicketController(JdbcTemplate jdbc, PythonAiClient python) {
        this.jdbc = jdbc;
        this.python = python;
    }

    @GetMapping("/list")
    public TableDataInfo list() {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT ticket_id, subject, detail, priority, status, session_id, assignee, remark, created_at, update_time FROM cs_ticket ORDER BY update_time DESC"
        );
        return new TableDataInfo(rows, rows.size());
    }

    @PostMapping("/sync")
    public AjaxResult sync() {
        List<Map<String, Object>> remote = python.listTickets(50);
        int n = 0;
        if (remote != null) {
            for (Map<String, Object> t : remote) {
                Object id = t.get("id");
                if (id == null) {
                    continue;
                }
                jdbc.update(
                        """
                        MERGE INTO cs_ticket (ticket_id, subject, detail, priority, status, session_id, created_at, update_time)
                        KEY (ticket_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """,
                        String.valueOf(id),
                        t.get("subject"),
                        t.get("detail"),
                        t.get("priority"),
                        t.get("status"),
                        String.valueOf(t.getOrDefault("session_id", "")),
                        t.get("created_at")
                );
                n++;
            }
        }
        return AjaxResult.success("已同步 " + n + " 条工单", Map.of("count", n));
    }

    @PutMapping("/{ticketId}")
    public AjaxResult update(@PathVariable String ticketId, @RequestBody Map<String, String> body) {
        ensure(ticketId);
        String status = body.get("status");
        if (status != null && !status.isBlank()) {
            python.patchTicket(ticketId, status);
            jdbc.update("UPDATE cs_ticket SET status=?, update_time=CURRENT_TIMESTAMP WHERE ticket_id=?", status, ticketId);
        }
        if (body.containsKey("assignee")) {
            jdbc.update("UPDATE cs_ticket SET assignee=?, update_time=CURRENT_TIMESTAMP WHERE ticket_id=?", body.get("assignee"), ticketId);
        }
        if (body.containsKey("remark")) {
            jdbc.update("UPDATE cs_ticket SET remark=?, update_time=CURRENT_TIMESTAMP WHERE ticket_id=?", body.get("remark"), ticketId);
        }
        return AjaxResult.success();
    }

    @PostMapping("/{ticketId}/assign")
    public AjaxResult assign(@PathVariable String ticketId, @RequestBody Map<String, String> body) {
        ensure(ticketId);
        String assignee = body.getOrDefault("assignee", "");
        if (assignee.isBlank()) {
            throw new ServiceException(400, "assignee 不能为空");
        }
        jdbc.update("UPDATE cs_ticket SET assignee=?, update_time=CURRENT_TIMESTAMP WHERE ticket_id=?", assignee, ticketId);
        return AjaxResult.success();
    }

    private void ensure(String ticketId) {
        Integer n = jdbc.queryForObject("SELECT COUNT(1) FROM cs_ticket WHERE ticket_id=?", Integer.class, ticketId);
        if (n == null || n == 0) {
            throw new ServiceException(404, "工单不存在，先点同步");
        }
    }
}
