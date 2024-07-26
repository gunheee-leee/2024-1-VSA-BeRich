package com.berich.stock_bot.entity;

import java.time.LocalDateTime;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Getter
@Setter
@Entity
public class Account {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id", updatable = false)
    private Long id;

    //계좌번호
    @Column(name = "accountNum", nullable =false, unique = true)
    private Long accountNum;
    //appkey
    @Column(nullable =false, unique = true)
    private String appKey;
    //appsecret
    @Column(nullable =false, unique = true)
    private String appSecret;
    //계좌 엑세스 토큰
    @Column(nullable =true, length = 500, updatable = true)
    private String accountAccessToken;

    @Column(nullable = true, updatable=true)
    private LocalDateTime expiredAt;

    @Column(name = "user_id", nullable =false, unique = true)
    private Long userId;

    @Builder
    public Account(Long accountNum, String appKey, String appSecret, String accountAccessToken, LocalDateTime expiredAt,Long userId){
        this.accountNum = accountNum;
        this.appKey = appKey;
        this.appSecret = appSecret;
        this.accountAccessToken = accountAccessToken;
        this.expiredAt = expiredAt;
        this.userId = userId;
    }



}
