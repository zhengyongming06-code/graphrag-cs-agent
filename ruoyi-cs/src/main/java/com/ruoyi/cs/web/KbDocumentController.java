package com.ruoyi.cs.web;

import com.ruoyi.cs.common.AjaxResult;
import com.ruoyi.cs.common.ServiceException;
import com.ruoyi.cs.common.TableDataInfo;
import com.ruoyi.cs.python.PythonAiClient;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.sql.PreparedStatement;
import java.sql.Statement;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/kb/document")
@PreAuthorize("hasAnyRole('ADMIN','KB')")
public class KbDocumentController {
    private final JdbcTemplate jdbc;
    private final PythonAiClient python;

    public KbDocumentController(JdbcTemplate jdbc, PythonAiClient python) {
        this.jdbc = jdbc;
        this.python = python;
    }

    @GetMapping("/list")
    public TableDataInfo list() {
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT id, title, category, source, status, neo4j_document_id, chunk_count, entity_count, create_by, create_time, update_time FROM kb_document ORDER BY id DESC"
        );
        return new TableDataInfo(rows, rows.size());
    }

    @GetMapping("/{id}")
    public AjaxResult get(@PathVariable long id) {
        return AjaxResult.success(one(id));
    }

    @PostMapping
    public AjaxResult create(@RequestBody Map<String, String> body, Authentication auth) {
        KeyHolder keys = new GeneratedKeyHolder();
        jdbc.update(con -> {
            PreparedStatement ps = con.prepareStatement(
                    "INSERT INTO kb_document (title, category, source, content, status, create_by) VALUES (?,?,?,?, 'draft', ?)",
                    Statement.RETURN_GENERATED_KEYS
            );
            ps.setString(1, required(body, "title"));
            ps.setString(2, body.getOrDefault("category", "general"));
            ps.setString(3, body.getOrDefault("source", "ruoyi"));
            ps.setString(4, required(body, "content"));
            ps.setString(5, auth.getName());
            return ps;
        }, keys);
        Number id = keys.getKey();
        if (id != null) {
            jdbc.update("UPDATE kb_document SET neo4j_document_id = ? WHERE id = ?", "kb-" + id.longValue(), id.longValue());
        }
        return AjaxResult.success(Map.of("id", id == null ? 0 : id.longValue()));
    }

    @PutMapping("/{id}")
    public AjaxResult update(@PathVariable long id, @RequestBody Map<String, String> body) {
        one(id);
        jdbc.update(
                "UPDATE kb_document SET title=?, category=?, source=?, content=?, status='draft', update_time=CURRENT_TIMESTAMP WHERE id=?",
                required(body, "title"),
                body.getOrDefault("category", "general"),
                body.getOrDefault("source", "ruoyi"),
                required(body, "content"),
                id
        );
        return AjaxResult.success();
    }

    @PostMapping("/{id}/publish")
    public AjaxResult publish(@PathVariable long id) {
        Map<String, Object> doc = one(id);
        String graphId = String.valueOf(doc.get("neo4j_document_id"));
        if (graphId.isBlank() || "null".equals(graphId)) {
            graphId = "kb-" + id;
            jdbc.update("UPDATE kb_document SET neo4j_document_id=? WHERE id=?", graphId, id);
        }
        Map<String, Object> py = python.ingest(
                graphId,
                String.valueOf(doc.get("title")),
                String.valueOf(doc.get("content")),
                String.valueOf(doc.getOrDefault("source", "ruoyi")),
                String.valueOf(doc.getOrDefault("category", "general"))
        );
        jdbc.update(
                "UPDATE kb_document SET status='published', chunk_count=?, entity_count=?, update_time=CURRENT_TIMESTAMP WHERE id=?",
                py.getOrDefault("chunk_count", 0),
                py.getOrDefault("entity_count", 0),
                id
        );
        return AjaxResult.success("已发布到 Python 图库", py);
    }

    @PostMapping("/{id}/offline")
    public AjaxResult offline(@PathVariable long id) {
        Map<String, Object> doc = one(id);
        String graphId = String.valueOf(doc.get("neo4j_document_id"));
        if (graphId != null && !graphId.isBlank() && !"null".equals(graphId)) {
            python.deleteDocument(graphId);
        }
        jdbc.update("UPDATE kb_document SET status='offline', update_time=CURRENT_TIMESTAMP WHERE id=?", id);
        return AjaxResult.success("已下架");
    }

    @DeleteMapping("/{id}")
    public AjaxResult delete(@PathVariable long id) {
        Map<String, Object> doc = one(id);
        String graphId = String.valueOf(doc.get("neo4j_document_id"));
        if (graphId != null && !graphId.isBlank() && !"null".equals(graphId)) {
            python.deleteDocument(graphId);
        }
        jdbc.update("DELETE FROM kb_document WHERE id=?", id);
        return AjaxResult.success();
    }

    private Map<String, Object> one(long id) {
        List<Map<String, Object>> rows = jdbc.queryForList("SELECT * FROM kb_document WHERE id=?", id);
        if (rows.isEmpty()) {
            throw new ServiceException(404, "文档不存在");
        }
        return rows.get(0);
    }

    private static String required(Map<String, String> body, String key) {
        String v = body.get(key);
        if (v == null || v.isBlank()) {
            throw new ServiceException(400, key + " 不能为空");
        }
        return v;
    }
}
