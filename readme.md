# chatGPT lineBot on AWS lambda

## 環境構築
1. lineのAPI設定を行う
   LINE_CHANNEL_ACCESS_TOKEN を取得する
1. awsの設定
    1. apiゲートウェイ作成
    1. ECRでレポジトリ作成
        1. このレポジトリのコンテナ化
    1. lambdaでコンテナベースで関数作成
    1. AuroraDBでテーブル作成
        テーブル項目は以下
        - LineUserID: 文字列(文字列)
        - Timestamp: 数値(ソートキー)
        - ChatContent: json
    1. lambdaの環境変数に値を入力
        - LINE_CHANNEL_ACCESS_TOKEN: LINEのAPIトークン
        - OPENAI_APIKEY: openAIのAPIトークン
        - LOG_LEVEL: "CRITICAL", "DEBUG"など
        - RECORD_FETCH_NUM: int 
        - DO_LINE_REPLY: 1でリプライ送る、0ならばリプライしない(デバッグ用)
        - AES_KEY: DBの暗号化キー
1. 反映方法
    ```
    $ aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com
    $ docker build -t line-chat-with-ory-repository .
    $ docker tag line-chat-with-ory-repository:latest <account-id>.dkr.ecr.ap-northeast-1.amazonaws.com/<repo-name>:latest
    $ docker push <account-id>.dkr.ecr.am-northeast-1.amazonaws.com/<repo-name>:latest
    ```