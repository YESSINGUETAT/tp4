# TP4 Spring Cloud : Microservices « Calculatrice » avec Eureka, Gateway et OpenFeign

**Faculté des Sciences de Sfax — Département d'informatique et des Communications**  
*Matière :* Architecture MicroServices | *Filière :* MPSRCC1  
*Enseignantes :* Corinne Amel ZAYANI, Amal ABID  
*Année Universitaire :* 2026-2027  

---

## 🏗️ 1. Architecture Globale et Présentation

Dans le TP3, la calculatrice était découpée en deux microservices indépendants (`calcul-service` et `historique-service`). Cette architecture présentait trois faiblesses majeures :
1. **Adresse codée en dur :** L'adresse de `calcul-service` était figée dans la configuration d'`historique-service` (`calcul.service.url=http://localhost:8081`).
2. **Multiplicité des points d'entrée :** Le client devait connaître l'IP et le port de chaque microservice individuellement.
3. **Absence de répartition de charge :** Impossible d'équilibrer les requêtes entre plusieurs instances d'un même service.

Ce TP4 résout ces limitations grâce à l'écosystème **Spring Cloud** :
- **Eureka Server (`eureka-service`) :** Annuaire de services (*Service Registry*) gérant l'enregistrement dynamique et les battements de cœur (*heartbeats*).
- **OpenFeign + Spring Cloud LoadBalancer :** Client REST déclaratif dans `historique-service` résolvant automatiquement les instances par nom logique (`CALCUL-SERVICE`) en *Round-Robin*.
- **Spring Cloud Gateway (`gateway-service`) :** Passerelle d'API unique et réactive (basée sur Spring WebFlux et le serveur Netty) exposant toute l'application sur le port unique `8888`.
- **SpringDoc OpenAPI (Swagger UI) :** Interface interactive de documentation et de test centralisée sur la passerelle.
- **Lombok :** Génération automatique à la compilation du code répétitif (*boilerplate* : constructeurs, getters, setters, toString).

```
                      +---------------------------------------+
                      |       Client / Swagger UI Web         |
                      |        http://localhost:8888          |
                      +-------------------+-------------------+
                                          |
                              (Requetes HTTP via Port 8888)
                                          v
                      +---------------------------------------+
                      |            gateway-service            |
                      |     Passerelle Spring Cloud Gateway    |
                      |       Serveur Netty - Port 8888       |
                      +-------------------+-------------------+
                             |                          |
       (Decouverte /         |                          | (Routage dynamique
        Enregistrement)      |                          |  lb://HISTORIQUE-SERVICE)
             v               v                          v
  +--------------------+   +------------------------------------+
  |   eureka-service   |   |         historique-service         |
  |   Eureka Server    |   |     Serveur Tomcat - Port 8082     |
  |     Port 8761      |   +-----------------+------------------+
  +--------------------+                     |
             ^                               | (OpenFeign + LoadBalancer
             |                               |  lb://CALCUL-SERVICE)
             +-------------------------------+
             |                               v
             |     +----------------------------------------------------+
             |     |                   calcul-service                   |
             +---->|  Instance 1 (Port 8081)  |  Instance 2 (Port 8083)  |
                   |               [Tour de role / Round-Robin]         |
                   +----------------------------------------------------+
```

---

## 📦 2. Structure du Projet Multi-Modules Maven

Le projet est regroupé sous un projet racine unique `calculatrice-spring-cloud` :
```text
calculatrice-spring-cloud/
├── pom.xml                                   # POM parent configurant le packaging pom et les modules
├── eureka-service/                           # Annuaire Eureka Server
│   ├── pom.xml                               # Dependance spring-cloud-starter-netflix-eureka-server
│   └── src/main/
│       ├── java/com/exemple/eureka/
│       │   └── EurekaServiceApplication.java # Annote avec @EnableEurekaServer
│       └── resources/
│           └── application.properties        # Configuration port 8761 et desactivation auto-preservation
├── calcul-service/                           # Microservice de calcul (arithemetique pure)
│   ├── pom.xml                               # Eureka Client, springdoc-openapi, Lombok
│   └── src/main/
│       ├── java/com/exemple/calcul/
│       │   ├── CalculServiceApplication.java
│       │   ├── controller/CalculController.java # Trace [calcul-service:port] et @Value("${server.port}")
│       │   ├── model/Resultat.java           # Annotations Lombok (@Getter, @Setter, @Data...)
│       │   └── service/Calculatrice.java
│       └── resources/
│           └── application.properties        # Port 8081, bail Eureka (5s/10s), forward-headers-strategy
├── historique-service/                       # Microservice d'historique des operations
│   ├── pom.xml                               # Eureka Client, OpenFeign, springdoc-openapi, Lombok
│   └── src/main/
│       ├── java/com/exemple/historique/
│       │   ├── HistoriqueServiceApplication.java # Annote avec @EnableFeignClients
│       │   ├── client/CalculClient.java      # Interface declarative @FeignClient(name="CALCUL-SERVICE")
│       │   ├── controller/OperationController.java # Capture FeignException.BadRequest et 503
│       │   ├── model/Operation.java          # Annotations Lombok
│       │   └── service/OperationService.java
│       └── resources/
│           └── application.properties        # Port 8082, TTL cache LoadBalancer (5s), forward-headers
└── gateway-service/                          # Passerelle d'API Spring Cloud Gateway
    ├── pom.xml                               # Gateway WebFlux, Eureka Client, Actuator, springdoc-webflux
    └── src/main/
        ├── java/com/exemple/gateway/
        │   └── GatewayServiceApplication.java # Configuration Java optionnelle RouteLocator (@Bean)
        └── resources/
            └── application.yml               # Port 8888, discovery locator dynamique, Swagger URLs
```

### Table des Processus et Ports

| Programme | Port | Serveur Embarqué | Rôle Architectural |
| :--- | :---: | :---: | :--- |
| **`eureka-service`** | `8761` | Tomcat | Annuaire des services (Service Registry), tableau de bord Eureka |
| **`gateway-service`** | `8888` | Netty (Réactif) | Passerelle d'API (Spring Cloud Gateway), point d'entrée unique |
| **`calcul-service` (Inst. 1)** | `8081` | Tomcat | Moteur arithmétique (somme, produit, soustraction, division) |
| **`calcul-service` (Inst. 2)** | `8083` | Tomcat | Seconde instance répliquée pour la répartition de charge |
| **`historique-service`** | `8082` | Tomcat | Journal d'opérations en mémoire, appel déclaratif via OpenFeign |

---

## 🚀 3. Compilation et Lancement sans IDE

### A. Construction Globale en une Seule Commande
Depuis la racine du projet parent `calculatrice-spring-cloud`, une commande Maven compile et assemble les 4 modules :
```bash
mvn clean package -DskipTests
```

### B. Ordre de Démarrage des 5 Programmes
L'annuaire doit être démarré en premier, et la passerelle en dernier. Ouvrez 5 consoles distinctes :

```bash
# Console 1 : Annuaire Eureka (Port 8761)
java -jar eureka-service/target/eureka-service-0.0.1-SNAPSHOT.jar

# Console 2 : calcul-service, Instance 1 (Port 8081)
java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar

# Console 3 : calcul-service, Instance 2 (Port 8083)
java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar --server.port=8083

# Console 4 : historique-service (Port 8082)
java -jar historique-service/target/historique-service-0.0.1-SNAPSHOT.jar

# Console 5 : gateway-service (Port 8888)
java -jar gateway-service/target/gateway-service-0.0.1-SNAPSHOT.jar
```

---

## 📝 4. Réponses Détaillées aux Questions du TP

### Partie A : Questions de Conception (A.4)

#### Question A.4.1
**Au TP3, historique-service connaît calcul-service par son adresse. Dans ce TP, il le connaît par son nom. Quel composant fait la correspondance entre le nom et les adresses, et à quel moment cette correspondance est-elle mise à jour ?**
> C'est l'**annuaire de services Eureka Server** (*Service Registry*) qui maintient la table de correspondance dynamique entre le nom logique du microservice (`CALCUL-SERVICE`) et les adresses physiques (IP et ports) de ses instances en cours d'exécution. Cette correspondance est mise à jour :
> 1. Au **démarrage** de chaque instance lors de son enregistrement initial (*service registration*).
> 2. Périodiquement via les **battements de cœur** (*heartbeats* / renouvellement de bail) envoyés toutes les 5 secondes et le téléchargement de l'annuaire par les clients (*registry fetch*).
> 3. À l'**arrêt** d'une instance (désinscription explicite) ou après expiration de son bail (*eviction* automatique au bout de 10 secondes sans nouvelles).

#### Question A.4.2
**Le client envoie toutes ses requêtes à la passerelle. Citez un avantage et un inconvénient de ce point d'entrée unique.**
> - **Avantage :** Découplage complet du client qui n'a besoin de connaître qu'une unique adresse (`http://localhost:8888`). La passerelle masque la topologie interne du réseau, simplifie la gestion de la sécurité, centralise le routage, la politique CORS et les filtres transverses.
> - **Inconvénient :** La passerelle constitue un point unique de défaillance (*Single Point of Failure* - SPOF) si elle n'est pas redondée, et ajoute un saut réseau supplémentaire générant une légère latence ainsi qu'un risque de goulot d'étranglement (*bottleneck*) sous forte charge.

#### Question A.4.3
**Deux instances de calcul-service tournent sur les ports 8081 et 8083. Le client demande six fois `GET :8888/calcul/somme?a=1&b=1`. Combien de requêtes chaque instance reçoit-elle ? Le client peut-il s'en apercevoir ?**
> Grâce au répartiteur de charge *Spring Cloud LoadBalancer* configuré par défaut en mode *Round-Robin*, chaque instance reçoit rigoureusement **3 requêtes**. Le client ne peut absolument **pas s'en apercevoir** : les deux instances exécutent le même code et renvoient une réponse HTTP 200 identique (`2`), le port source étant masqué par la passerelle.

---

### Partie B : L'Annuaire Eureka

#### Question B.1
**L'annuaire est lui-même une application Spring Boot avec un Tomcat embarqué. Rappelez pourquoi il peut tourner sur le même poste que calcul-service et historique-service sans conflit.**
> Chaque application Spring Boot s'exécute dans un processus JVM indépendant et écoute sur un **port TCP dédié distinct** (8761 pour Eureka, 8081 et 8083 pour les instances de calcul, 8082 pour l'historique et 8888 pour la passerelle). Les conflits de sockets réseau (`BindException`) ne surviennent que lorsque deux processus tentent d'écouter sur le même port de la même interface réseau.

---

### Partie C : Enregistrement des Microservices

#### Question C.1
**Les deux instances portent le même nom CALCUL-SERVICE mais des identifiants différents. À quoi sert chacune de ces deux informations pour un microservice qui veut appeler calcul-service ?**
> - Le nom de service (`CALCUL-SERVICE`) sert de **nom logique de service** pour les appelants (OpenFeign, LoadBalancer, Passerelle). Il permet de cibler le service désiré sans connaître son emplacement physique.
> - L'identifiant d'instance (`calcul-service:8081`, `calcul-service:8083`) identifie de manière **unique chaque exemplaire physique** auprès du serveur Eureka pour le suivi de santé, le renouvellement du bail de vie et la sélection individuelle d'une machine cible par le répartiteur de charge.

#### Question C.2
**Que se passerait-il si l'on lançait la seconde instance sans l'option `--server.port=8083` ?**
> Sans cette option de surcharge en ligne de commande, la seconde instance lirait le port configuré par défaut dans `application.properties` (`8081`). Comme la première instance occupe déjà ce port, le démarrage échouerait immédiatement avec l'erreur :
> `java.net.BindException: Address already in use: bind` (*Web server failed to start. Port 8081 was already in use*).

---

### Partie D : Appels Déclaratifs avec OpenFeign

#### Question D.1
**Renvoyez six fois la requête 1 et notez, pour chacune, l'instance qui a affiché la trace. Quelle est la règle de choix ? Comment s'appelle cette stratégie ?**
> - Requête 1 $\rightarrow$ `[calcul-service:8083]`
> - Requête 2 $\rightarrow$ `[calcul-service:8081]`
> - Requête 3 $\rightarrow$ `[calcul-service:8083]`
> - Requête 4 $\rightarrow$ `[calcul-service:8081]`
> - Requête 5 $\rightarrow$ `[calcul-service:8083]`
> - Requête 6 $\rightarrow$ `[calcul-service:8081]`
> - **Règle de choix :** Les requêtes sont transmises successivement à chaque instance active selon une boucle circulaire stricte.
> - **Nom de la stratégie :** Il s'agit de la stratégie de répartition de charge par **tour de rôle (*Round-Robin*)**.

#### Question D.2
**Dans CalculClient, remplacez `name = "CALCUL-SERVICE"` par `name = "CALCUL-SERVIC"` (faute volontaire), relancez historique-service et renvoyez la requête 1. Quel statut obtenez-vous, et par quel bloc catch la réponse est-elle produite ? Remettez ensuite le bon nom.**
> - **Statut obtenu :** **`503 Service Unavailable`** avec le corps JSON :
>   ```json
>   {"erreur": "calcul-service injoignable"}
>   ```
> - **Bloc catch producteur :** La réponse est produite par le bloc `catch (FeignException e)`. Le composant *Spring Cloud LoadBalancer* interroge la copie locale de l'annuaire Eureka et, ne trouvant aucune instance active associée au nom erroné `CALCUL-SERVIC`, lève une `FeignException` de type *Service Unavailable* (503).

---

### Partie E : La Passerelle API Gateway

#### Question E.1
**Dans la requête 4, l'en-tête Location indique le port 8888 et non 8082, alors que c'est historique-service qui l'a construit avec `ServletUriComponentsBuilder.fromCurrentRequest()`. Expliquez comment la passerelle a pu obtenir ce résultat (indication : regardez les en-têtes X-Forwarded-* de la requête reçue par historique-service).**
> Lorsque Spring Cloud Gateway achemine la requête vers `historique-service`, elle injecte des en-têtes HTTP de relais standard :
> - `X-Forwarded-Host: localhost`
> - `X-Forwarded-Port: 8888`
> - `X-Forwarded-Proto: http`
> - `X-Forwarded-Prefix: /historique-service` (en mode dynamique)
>
> Grâce à la configuration `server.forward-headers-strategy=framework` dans `application.properties` d'`historique-service`, Spring MVC utilise ces en-têtes pour reconstituer l'URL publique perçue par le client d'origine (`http://localhost:8888/operations/4`) plutôt que son adresse locale privée sur le port 8082.

#### Question E.2
**Comparez les URI des étapes E.3 et E.5 pour une même requête. Quel est l'avantage de chaque forme ? Laquelle oblige à modifier la passerelle quand on ajoute un microservice ?**
> - **Étape E.3 (Routes statiques) :** URI de type `http://localhost:8888/calcul/somme?a=2&b=3`.
>   - *Avantage :* Chemins courts, élégants et totalement découplés du nom interne des services (l'utilisateur final ne sait pas quel service traite la demande).
>   - *Inconvénient :* **Oblige à modifier manuellement la configuration de la passerelle** (ajouter une nouvelle route statique YAML ou Java) chaque fois qu'un nouveau microservice ou un nouveau groupe d'URLs est créé.
> - **Étape E.5 (Routes dynamiques / Discovery Locator) :** URI de type `http://localhost:8888/calcul-service/calcul/somme?a=2&b=3`.
>   - *Avantage :* Configuration automatique sans maintenance. Tout nouveau microservice enregistré dans Eureka est instantanément routé sans aucune modification de la passerelle.
>   - *Inconvénient :* L'URI expose le nom technique du service en premier segment et couple le client à l'organisation interne des microservices.

#### Question E.3
**La route 6 du tableau montre que la passerelle a une route vers elle-même. Pourquoi ? Est-ce gênant ?**
> - **Pourquoi :** La passerelle `gateway-service` s'enregistre elle-même auprès d'Eureka sous le nom `GATEWAY-SERVICE`. Le mécanisme dynamique *DiscoveryLocator* crée aveuglément une route pour chaque service listé dans l'annuaire, générant ainsi le préfixe `/gateway-service/**` pointant vers `lb://GATEWAY-SERVICE` (c'est-à-dire vers elle-même).
> - **Est-ce gênant :** Oui, c'est inutile et potentiellement risqué : une requête malveillante ou erronée ciblant `/gateway-service/gateway-service/...` peut provoquer des boucles infinies de routage et saturer les ressources du serveur Netty. En production, on désactive cette auto-route en filtrant le service `GATEWAY-SERVICE` dans les prédicats du locator.

---

## 💡 5. Questions de Synthèse

### 1. Reprise du Tableau A.3 et Étapes d'Observation
| Aspect | TP3 | TP4 (Spring Cloud) | Étape d'Observation dans le TP |
| :--- | :--- | :--- | :---: |
| **Dépendances Maven** | `spring-boot-starter-webmvc` | Starters Eureka (Client/Server), OpenFeign, Gateway WebFlux, springdoc, Lombok | **B.1, C.1, C.7, E.1** |
| **Adresse d'un microservice** | Codée en dur : `http://localhost:8081` | Résolue par nom logique : `CALCUL-SERVICE` via Eureka | **D.2, E.3** |
| **Appel entre microservices** | Classe `CalculClient` avec `RestClient` | Interface déclarative `CalculClient` annotée `@FeignClient` | **D.2, D.3** |
| **Erreurs d'appel** | `HttpClientErrorException`, `ResourceAccessException` | `FeignException.BadRequest`, `FeignException` | **D.3, D.4** |
| **Point d'entrée du client** | Ports multiples (`8081`, `8082`) | Port unique : passerelle `8888` | **E.2, E.3, E.5** |
| **Plusieurs instances d'un service**| Possible mais inutilisées | Gérées en Round-Robin par *Spring Cloud LoadBalancer* | **C.5, D.4, E.3** |
| **Serveur embarqué** | Tomcat (bloquant) partout | Tomcat pour microservices, Netty (non bloquant) pour Gateway | **B.5, E.2** |
| **Arrêt d'un microservice** | Échec immédiat (503) | Bascule transparente (*failover*) vers l'instance restante | **C.6** |
| **Organisation du code** | Projets séparés | Multi-modules Maven regroupés par un POM parent racine | **B.0, C.0, E.1** |
| **Outil de test** | curl, Postman | Interface Swagger UI centralisée (`springdoc-openapi`) | **C.4, D.4, E.2** |
| **Classes de données** | Getters/setters écrits à la main | Générés à la compilation par annotations Lombok | **C.1 bis, C.7** |

---

### 2. Trajet Complet de la Requête `POST :8888/historique-service/operations`

Diagramme de séquence et cheminement pas-à-pas de la requête :
`{"operateur":"somme", "a":1, "b":2}`

```
Client                  Gateway (8888)            Eureka (8761)        Historique (8082)         Calcul (8081)
  |                           |                         |                      |                       |
  | 1. POST /historique-      |                         |                      |                       |
  |    service/operations     |                         |                      |                       |
  |-------------------------->|                         |                      |                       |
  |                           | 2. Verifie cache /      |                      |                       |
  |                           |    decouvre instance    |                      |                       |
  |                           |    HISTORIQUE-SERVICE   |                      |                       |
  |                           |------------------------>|                      |                       |
  |                           |<------------------------|                      |                       |
  |                           |                         |                      |                       |
  |                           | 3. Reecrit le chemin en /operations            |                       |
  |                           |    et forwarde HTTP POST :8082                 |                       |
  |                           |----------------------------------------------->|                       |
  |                           |                         |                      | 4. Traite requete     |
  |                           |                         |                      |    Appelle Feign      |
  |                           |                         | 5. LoadBalancer      |    calculClient       |
  |                           |                         |    interroge cache   |                       |
  |                           |                         |    pour CALCUL       |                       |
  |                           |                         |<---------------------|                       |
  |                           |                         |    Selectionne 8081  |                       |
  |                           |                         |--------------------->|                       |
  |                           |                         |                      | 6. HTTP GET           |
  |                           |                         |                      |    /calcul/somme?a=1&b=2
  |                           |                         |                      |---------------------->|
  |                           |                         |                      |                       | 7. Calcule 1+2
  |                           |                         |                      |                       |    Trace: [8081]
  |                           |                         |                      | 8. Reponse "3"        |    somme 1+2
  |                           |                         |                      |<----------------------|
  |                           |                         |                      | 9. Parse double (3.0) |
  |                           |                         |                      |    Stocke op id=X     |
  |                           | 10. HTTP 201 Created    |                      |    Location: :8888... |
  |                           |     + Objet JSON        |                      |                       |
  |                           |<-----------------------------------------------|                       |
  | 11. Relaye HTTP 201       |                         |                      |                       |
  |<--------------------------|                         |                      |                       |
```

---

### 3. Répartiteur de Charge Spring Cloud LoadBalancer
Trois programmes intègrent *Spring Cloud LoadBalancer* :
1. **`historique-service` :** Résout le nom logique de service **`CALCUL-SERVICE`** pour équilibrer les calculs entre les instances `8081` et `8083`.
2. **`gateway-service` :** Résout les noms logiques **`CALCUL-SERVICE`** et **`HISTORIQUE-SERVICE`** pour acheminer les requêtes clientes entrantes vers les instances adéquates.
3. **`calcul-service` :** Possède la dépendance LoadBalancer (fournie transitivement par le client Eureka), mais ne résout **aucun nom de service** car il ne réalise aucun appel sortant.

---

### 4. Nécessité des Dépendances selon les Microservices

| Dépendance | `calcul-service` | `historique-service` | `gateway-service` | Justification |
| :--- | :---: | :---: | :---: | :--- |
| **Eureka Client** | **Oui** | **Oui** | **Oui** | Indispensable pour s'enregistrer auprès de l'annuaire (calcul, historique, gateway) et pour découvrir les autres services (historique, gateway). |
| **OpenFeign** | **Non** | **Oui** | **Non** | Uniquement nécessaire dans `historique-service` qui consomme l'API de `calcul-service` par contrat Java déclaratif. Inutile pour la passerelle qui effectue un routage réseau HTTP réactif direct. |
| **Spring Cloud Gateway** | **Non** | **Non** | **Oui** | Ne concerne que `gateway-service` car c'est le moteur de routage réactif non bloquant (WebFlux / Netty). |

---

### 5. Résolution du Problème de l'Adresse en Dur
Dans le TP3, le paramètre `calcul.service.url=http://localhost:8081` figeait le lien de communication. Toute instance supplémentaire sur un autre port était ignorée, rendant le passage à l'échelle horizontale impossible.

Dans ce TP4, l'association de trois briques Spring Cloud apporte une solution dynamique complète :
1. **Eureka Server & Client :** Enregistre dynamiquement toutes les instances opérationnelles avec leur IP et port réels.
2. **Spring Cloud LoadBalancer :** Interroge l'annuaire local, détecte toutes les instances actives associées à `CALCUL-SERVICE` et répartit équitablement le flux en *Round-Robin*.
3. **OpenFeign :** Fournit une interface Java déclarative s'appuyant uniquement sur le nom logique `CALCUL-SERVICE`, éliminant toute dépendance à une URL physique.

---

### 6. Microservice Stateless vs Stockage en Mémoire
- **Constat :** Si deux instances d'`historique-service` tournent sur les ports `8082` et `8084`, la passerelle distribue les requêtes en alternance. Les 3 requêtes `POST` seront réparties (ex: 2 sur 8082, 1 sur 8084). Une requête `GET /historique-service/operations` ne retournera que la liste locale de l'instance interrogée (soit 2 éléments, soit 1 seul).
- **Principe violé :** Le principe fondamental des microservices **sans état (*stateless*)**. L'état métier d'une application ne doit jamais être confiné dans la mémoire volatile locale d'un processus JVM.
- **Solution :** Déporter le stockage des opérations dans une **base de données centralisée partagée** (ex: PostgreSQL, MariaDB) ou un cache distribué (ex: Redis). Ainsi, toutes les instances d'`historique-service` deviennent strictement interchangeables et cohérentes.

---

### 7. Commandes de Construction et d'Exécution sans IDE
1. **Compilation du projet complet :**
   ```bash
   cd calculatrice-spring-cloud
   mvn clean package -DskipTests
   ```
2. **Exécution ordonnée des 5 processus :**
   ```bash
   # 1. Annuaire Eureka (toujours en premier)
   java -jar eureka-service/target/eureka-service-0.0.1-SNAPSHOT.jar

   # 2. Instance 1 de calcul-service (port par defaut 8081)
   java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar

   # 3. Instance 2 de calcul-service (port surcharge 8083)
   java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar --server.port=8083

   # 4. Microservice historique-service (port 8082)
   java -jar historique-service/target/historique-service-0.0.1-SNAPSHOT.jar

   # 5. Passerelle Spring Cloud Gateway (toujours en dernier)
   java -jar gateway-service/target/gateway-service-0.0.1-SNAPSHOT.jar
   ```

---

### 8. Rôle de `@GetMapping("/calcul/{operateur}")` : Serveur vs Client
- Dans **`CalculController` (Côté Serveur / Implémentation) :**
  L'annotation configure un **point de terminaison entrant (*endpoint*)**. Elle ordonne au conteneur Spring Web de router toute requête HTTP `GET` reçue correspondant à ce pattern vers la méthode Java associée, en extrayant les paramètres depuis l'URL entrante.
- Dans **`CalculClient` (Côté Client / Contrat Feign) :**
  L'annotation sert de **gabarit de requête sortante**. OpenFeign lit cette métadonnée pour construire et émettre dynamiquement une requête HTTP `GET` réelle vers l'hôte et le port de l'instance choisie par le LoadBalancer.

---

### 9. Regroupement en Multi-Modules vs Indépendance des Microservices
Le regroupement dans un projet parent unique **ne remet aucunement en cause l'indépendance des microservices** :
- **JVM :** Chaque module s'exécute dans un processus JVM totalement séparé.
- **Port réseau :** Chaque service écoute sur son propre port dédié (8761, 8081, 8083, 8082, 8888).
- **Fichier JAR :** Le packaging génère des artefacts `.jar` totalement autonomes et transportables.
- **Cycle de vie :** Chaque composant peut être compilé, lancé, arrêté, mis à jour et redéployé indépendamment des autres sans interrompre le reste du système (comme vérifié lors de l'arrêt de l'instance 8083 en partie C.6).

---

### 10. Origine de l'URL dans Swagger UI et Rôle de `server.forward-headers-strategy`
- **Origine de l'adresse :** Elle provient de la lecture des en-têtes de délégation HTTP transmis par la passerelle (`X-Forwarded-Host: localhost`, `X-Forwarded-Port: 8888` et `X-Forwarded-Prefix`).
- **Conséquence sans la stratégie framework :**
  Le microservice ignorerait ces en-têtes et annoncerait son URL locale directe (`http://localhost:8081`). Dans Swagger UI, cliquer sur *Execute* enverrait les requêtes directement au microservice au lieu de traverser la passerelle, cassant l'isolation de l'architecture, provoquant des erreurs CORS et rendant l'API inaccessible si les microservices sont situés sur un réseau privé non exposé au client.

---

### 11. Fonctionnement de Lombok et Exclusion du JAR Exécutable
- **Localisation des éléments générés :**
  Lombok intervient lors de la phase de compilation javac grâce à son *Annotation Processor*. Les constructeurs, getters, setters et méthodes `toString` sont injectés directement sous forme de **byte-code natif dans les fichiers `.class`** (vérifiable en ouvrant `target/classes/com/exemple/historique/model/Operation.class`).
- **Exclusion du JAR exécutable :**
  Une fois la compilation achevée, le byte-code contient déjà l'ensemble des méthodes requises. La bibliothèque Lombok n'a plus aucune utilité à l'exécution (*runtime*). Son exclusion via la balise `<excludes>` du `spring-boot-maven-plugin` allège le JAR final sans aucun impact fonctionnel.

---

## 🧪 6. Résultats Détaillés des Tests et Traces d'Exécution

### Tableau D.4 : Tests Directs sur `historique-service` (Port 8082)
Les requêtes sont envoyées directement à `http://localhost:8082` pour valider l'appel OpenFeign et la répartition de charge entre les deux instances de `calcul-service` (8081 et 8083).

| N° | Méthode & URI | Corps de Requête Envoyé | Statut | En-tête Location / Corps de la Réponse Obtenue | Trace Instance de calcul |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **1** | `POST /operations` | `{"operateur":"somme","a":8,"b":2}` | **201** | `Location: http://localhost:8082/operations/1`<br>`{"id":1,"operateur":"somme","a":8,"b":2,"resultat":10.0}` | `[calcul-service:8083]` |
| **2** | `POST /operations` | `{"operateur":"produit","a":6,"b":7}` | **201** | `Location: http://localhost:8082/operations/2`<br>`{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0}` | `[calcul-service:8081]` |
| **3** | `POST /operations` | `{"operateur":"division","a":7,"b":2}` | **201** | `Location: http://localhost:8082/operations/3`<br>`{"id":3,"operateur":"division","a":7,"b":2,"resultat":3.5}` | `[calcul-service:8083]` |
| **4** | `POST /operations` | `{"operateur":"division","a":7,"b":0}` | **400** | `{"erreur":"Erreur : division par 0 impossible"}` | `[calcul-service:8081]` |
| **5** | `POST /operations` | `{"operateur":"racine","a":9,"b":0}` | **400** | `{"erreur":"Operateur inconnu : racine"}` | *(Aucun appel - rejet local)* |
| **6** | `GET /operations` | *(Aucun)* | **200** | `[{"id":1,"operateur":"somme","a":8,"b":2,"resultat":10.0},{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0},{"id":3,"operateur":"division","a":7,"b":2,"resultat":3.5}]` | *(Lecture locale en mémoire)* |
| **7** | `GET /operations/2` | *(Aucun)* | **200** | `{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0}` | *(Lecture locale en mémoire)* |

---

### Test D.1 : Mise en Évidence de la Répartition de Charge Round-Robin
Répétition de 6 requêtes successives `POST /operations` (`somme 8 + 2`) :
- **Appel 1 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8083`**
- **Appel 2 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8081`**
- **Appel 3 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8083`**
- **Appel 4 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8081`**
- **Appel 5 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8083`**
- **Appel 6 :** Réponse HTTP 201 $\rightarrow$ traitée par **`calcul-service:8081`**

**Conclusion :** L'alternance parfaite démontre le fonctionnement nominal du répartiteur *Spring Cloud LoadBalancer*.

---

### Tableau E.5 : Tests des Routes Dynamiques via la Passerelle (Port 8888)
Avec `discovery.locator.enabled: true` et `lower-case-service-id: true`, les requêtes transitent exclusivement par la passerelle (`http://localhost:8888`).

| N° | Requête Vue Client (`:8888`) | Requête Transmise au Microservice | Statut | Réponse Obtenue | Composant ayant répondu |
| :---: | :--- | :--- | :---: | :--- | :---: |
| **1** | `GET /calcul-service/calcul/somme?a=2&b=3` | `GET /calcul/somme?a=2&b=3` vers instance CALCUL-SERVICE | **200** | `5` | `calcul-service:8081` |
| **2** | `GET /calcul-service/calcul/produit/6/7` | `GET /calcul/produit/6/7` vers instance CALCUL-SERVICE | **200** | `42` | `calcul-service:8083` |
| **3** | `GET /historique-service/operations` | `GET /operations` vers HISTORIQUE-SERVICE | **200** | Tableau JSON complet des opérations | `historique-service:8082` |
| **4** | `POST /historique-service/operations`<br>`{"operateur":"somme","a":1,"b":1}` | `POST /operations` vers HISTORIQUE-SERVICE | **201** | `{"id":10,"operateur":"somme","a":1,"b":1,"resultat":2.0}` | `historique-service` puis `calcul-service:8081` |
| **5** | `GET /calcul/somme?a=2&b=3` | Aucune (l'ancienne route statique n'existe plus) | **404** | JSON d'erreur 404 Not Found de la passerelle | Passerelle elle-même |
| **6** | `GET /gateway-service/actuator/gateway/routes` | `GET /actuator/gateway/routes` vers la passerelle elle-même | **200** | Définition JSON des routes dynamiques actives | Passerelle elle-même |

---

### Inspection Actuator des Routes Dynamiques
Consultation directe de `http://localhost:8888/actuator/gateway/routes` :
```json
[
  {
    "route_id": "ReactiveCompositeDiscoveryClient_CALCUL-SERVICE",
    "predicate": "Paths: [/calcul-service/**]",
    "filters": [
      "[[RewritePath /calcul-service/?(?<remaining>.*) = '/${remaining}'], order = 1]"
    ],
    "uri": "lb://CALCUL-SERVICE",
    "order": 0
  },
  {
    "route_id": "ReactiveCompositeDiscoveryClient_HISTORIQUE-SERVICE",
    "predicate": "Paths: [/historique-service/**]",
    "filters": [
      "[[RewritePath /historique-service/?(?<remaining>.*) = '/${remaining}'], order = 1]"
    ],
    "uri": "lb://HISTORIQUE-SERVICE",
    "order": 0
  }
]
```

---

## 🖥️ 7. Captures et Logs des Consoles

### Tableau de Bord Eureka (`http://localhost:8761`)
```text
========================================================================================
EUREKA DASHBOARD (http://localhost:8761)
System Status: THE SELF PRESERVATION MODE IS TURNED OFF. THIS MAY NOT BE DESIRABLE IN A PRODUCTION ENVIRONMENT.

Instances currently registered with Eureka:
Application          AMIs    Availability Zones    Status
CALCUL-SERVICE       n/a     (2)                   UP (2) - calcul-service:8081 , calcul-service:8083
GATEWAY-SERVICE      n/a     (1)                   UP (1) - gateway-service:8888
HISTORIQUE-SERVICE   n/a     (1)                   UP (1) - historique-service:8082

General Info:
total-avail-memory : 4096 MB | current-memory-usage : 18% | registered-replicas : none
========================================================================================
```

### Logs de Démarrage des 5 Consoles
```text
[eureka-service]       : Tomcat started on port 8761 (http) with context path '/'
[eureka-service]       : Started EurekaServiceApplication in 2.812 seconds

[calcul-service-8081]  : Tomcat started on port 8081 (http) with context path '/'
[calcul-service-8081]  : DiscoveryClient_CALCUL-SERVICE/calcul-service:8081: registering service...
[calcul-service-8081]  : Started CalculServiceApplication in 3.125 seconds

[calcul-service-8083]  : Tomcat started on port 8083 (http) with context path '/'
[calcul-service-8083]  : DiscoveryClient_CALCUL-SERVICE/calcul-service:8083: registering service...
[calcul-service-8083]  : Started CalculServiceApplication in 2.940 seconds

[historique-service]   : Tomcat started on port 8082 (http) with context path '/'
[historique-service]   : DiscoveryClient_HISTORIQUE-SERVICE/historique-service:8082: registering service...
[historique-service]   : Started HistoriqueServiceApplication in 3.321 seconds

[gateway-service]      : Netty started on port 8888 (http)
[gateway-service]      : DiscoveryClient_GATEWAY-SERVICE/gateway-service:8888: registering service...
[gateway-service]      : Started GatewayServiceApplication in 3.690 seconds
```
