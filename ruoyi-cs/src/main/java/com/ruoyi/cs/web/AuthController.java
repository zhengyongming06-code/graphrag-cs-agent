package com.ruoyi.cs.web;

import com.ruoyi.cs.common.AjaxResult;
import com.ruoyi.cs.common.ServiceException;
import com.ruoyi.cs.security.JwtService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

import java.security.Principal;
import java.util.Arrays;
import java.util.List;
import java.util.Map;

@RestController
public class AuthController {
    private final JdbcTemplate jdbc;
    private final PasswordEncoder encoder;
    private final JwtService jwt;

    public AuthController(JdbcTemplate jdbc, PasswordEncoder encoder, JwtService jwt) {
        this.jdbc = jdbc;
        this.encoder = encoder;
        this.jwt = jwt;
    }

    @PostMapping("/login")
    public AjaxResult login(@RequestBody Map<String, String> body) {
        String username = body.getOrDefault("username", "");
        String password = body.getOrDefault("password", "");
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT username, password, nick_name, roles FROM cs_user WHERE username = ? AND status = '0'",
                username
        );
        if (rows.isEmpty()) {
            throw new ServiceException(401, "用户不存在");
        }
        Map<String, Object> user = rows.get(0);
        String stored = String.valueOf(user.get("password")).replace("{noop}", "");
        if (!encoder.matches(password, stored)) {
            throw new ServiceException(401, "密码错误");
        }
        List<String> roles = Arrays.stream(String.valueOf(user.get("roles")).split(","))
                .map(String::trim).filter(s -> !s.isEmpty()).toList();
        AjaxResult r = AjaxResult.success();
        r.put("token", jwt.issue(username, roles));
        return r;
    }

    @GetMapping("/getInfo")
    public AjaxResult info(Principal principal) {
        Map<String, Object> user = jdbc.queryForMap(
                "SELECT username, nick_name, roles FROM cs_user WHERE username = ?",
                principal.getName()
        );
        List<String> roles = Arrays.stream(String.valueOf(user.get("roles")).split(",")).toList();
        return AjaxResult.success(Map.of(
                "user", Map.of("userName", user.get("username"), "nickName", user.get("nick_name")),
                "roles", roles,
                "permissions", roles.stream().map(r -> r + ":*").toList()
        ));
    }

    @GetMapping("/health")
    public AjaxResult health() {
        return AjaxResult.success(Map.of("app", "ruoyi-cs"));
    }
}
