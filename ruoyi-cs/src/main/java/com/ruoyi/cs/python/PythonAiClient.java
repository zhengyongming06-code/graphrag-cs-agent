package com.ruoyi.cs.python;

import com.ruoyi.cs.common.ServiceException;
import org.springframework.http.HttpStatusCode;
import org.springframework.http.MediaType;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import java.time.Duration;
import java.util.List;
import java.util.Map;

@Component
public class PythonAiClient {
    private final RestClient client;

    public PythonAiClient(PythonProperties props) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(Duration.ofSeconds(5));
        factory.setReadTimeout(Duration.ofSeconds(30));
        this.client = RestClient.builder()
                .baseUrl(props.getBaseUrl())
                .requestFactory(factory)
                .defaultHeader("X-Service-Token", props.getServiceToken())
                .build();
    }

    public Map<String, Object> ingest(String documentId, String title, String content, String source, String category) {
        return post("/api/knowledge/ingest", Map.of(
                "document_id", documentId,
                "title", title,
                "content", content,
                "source", source,
                "category", category
        ));
    }

    public void deleteDocument(String documentId) {
        client.delete()
                .uri("/api/knowledge/documents/{id}", documentId)
                .retrieve()
                .onStatus(HttpStatusCode::isError, (req, res) -> {
                    if (res.getStatusCode().value() != 404) {
                        throw new ServiceException("Python 删除文档失败: " + res.getStatusCode());
                    }
                })
                .toBodilessEntity();
    }

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> listSessions(int limit) {
        return client.get()
                .uri(uri -> uri.path("/api/sessions").queryParam("limit", limit).build())
                .retrieve()
                .body(List.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> getSession(String sessionId) {
        return client.get()
                .uri("/api/sessions/{id}", sessionId)
                .retrieve()
                .onStatus(HttpStatusCode::is4xxClientError, (req, res) -> {
                    throw new ServiceException(404, "Python 会话不存在");
                })
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    public List<Map<String, Object>> listTickets(int limit) {
        return client.get()
                .uri(uri -> uri.path("/api/tickets").queryParam("limit", limit).build())
                .retrieve()
                .body(List.class);
    }

    @SuppressWarnings("unchecked")
    public Map<String, Object> patchTicket(String ticketId, String status) {
        return client.patch()
                .uri("/api/tickets/{id}", ticketId)
                .contentType(MediaType.APPLICATION_JSON)
                .body(Map.of("status", status))
                .retrieve()
                .onStatus(HttpStatusCode::is4xxClientError, (req, res) -> {
                    throw new ServiceException(404, "Python 工单不存在");
                })
                .body(Map.class);
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> post(String path, Map<String, Object> body) {
        return client.post()
                .uri(path)
                .contentType(MediaType.APPLICATION_JSON)
                .body(body)
                .retrieve()
                .onStatus(HttpStatusCode::isError, (req, res) -> {
                    throw new ServiceException("Python 调用失败: " + res.getStatusCode());
                })
                .body(Map.class);
    }
}
