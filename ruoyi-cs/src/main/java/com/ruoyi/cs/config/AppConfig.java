package com.ruoyi.cs.config;

import com.ruoyi.cs.common.AjaxResult;
import com.ruoyi.cs.common.ServiceException;
import com.ruoyi.cs.python.PythonProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@EnableConfigurationProperties(PythonProperties.class)
@org.springframework.context.annotation.Configuration
public class AppConfig implements WebMvcConfigurer {
    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/**").allowedOrigins("*").allowedMethods("*").allowedHeaders("*");
    }

    @RestControllerAdvice
    public static class Errors {
        @ExceptionHandler(ServiceException.class)
        public ResponseEntity<AjaxResult> service(ServiceException ex) {
            return ResponseEntity.status(ex.getCode() >= 400 && ex.getCode() < 600 ? ex.getCode() : 500)
                    .body(AjaxResult.error(ex.getCode(), ex.getMessage()));
        }

        @ExceptionHandler(ResourceAccessException.class)
        public AjaxResult pythonDown(ResourceAccessException ex) {
            return AjaxResult.error("连不上 Python AI 服务（默认 127.0.0.1:8000）");
        }
    }
}
