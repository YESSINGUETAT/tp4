# TP4 Spring Cloud : Microservices « Calculatrice »
## Réponses aux Questions du TP

**Faculté des Sciences de Sfax — Département d'informatique et des Communications**  
*Matière :* Architecture MicroServices | *Filière :* MPSRCC1  
*Enseignantes :* Corinne Amel ZAYANI, Amal ABID  
*Année Universitaire :* 2026-2027  

---

## 📌 Partie A : Du TP3 à Spring Cloud — Questions de Conception

### Question A.4.1
**Au TP3, `historique-service` connaît `calcul-service` par son adresse. Dans ce TP, il le connaît par son nom. Quel composant fait la correspondance entre le nom et les adresses, et à quel moment cette correspondance est-elle mise à jour ?**

> C'est l'**annuaire de services Eureka Server** (*Service Registry*) qui maintient la correspondance dynamique entre le nom logique (`CALCUL-SERVICE`) et les adresses physiques (IP et port) des instances.  
> Cette correspondance est mise à jour :
> 1. Au **démarrage** de l'instance lors de son inscription (*service registration*).
> 2. Périodiquement via les **battements de cœur** (*heartbeats* envoyés toutes les 5 s) et le rafraîchissement régulier de l'annuaire par les clients.
> 3. À l'**arrêt** de l'instance (désinscription explicite) ou après expiration de son bail (*éviction* automatique après 10 s sans nouvelles).

---

### Question A.4.2
**Le client envoie toutes ses requêtes à la passerelle. Citez un avantage et un inconvénient de ce point d'entrée unique.**

> - **Avantage :** **Découplage et simplification client** : le client n'a besoin de connaître qu'une adresse et un port uniques (`http://localhost:8888`). La topologie interne est masquée, et la sécurité/CORS/routage sont centralisés.
> - **Inconvénient :** **Point unique de défaillance (*SPOF*)** : si la passerelle tombe et n'est pas redondée, l'ensemble du système devient inaccessible. Elle introduit aussi un saut réseau supplémentaire (légère latence) et un goulot d'étranglement potentiel sous forte charge.

---

### Question A.4.3
**Deux instances de `calcul-service` tournent sur les ports 8081 et 8083. Le client demande six fois `GET :8888/calcul/somme?a=1&b=1`. Combien de requêtes chaque instance reçoit-elle ? Le client peut-il s'en apercevoir ?**

> - Grâce au répartiteur de charge *Spring Cloud LoadBalancer*, chaque instance reçoit exactement **3 requêtes** selon une alternance équitable (*Round-Robin*).
> - Le client **ne peut pas s'en apercevoir** : les deux instances exécutent le même traitement arithmétique et renvoient une réponse identique (`2`, code HTTP 200). L'adresse et le port de l'instance réelle sont masqués par la passerelle.

---

## 📌 Partie B : L'Annuaire Eureka

### Question B.1
**L'annuaire est lui-même une application Spring Boot avec un Tomcat embarqué. Rappelez pourquoi il peut tourner sur le même poste que `calcul-service` et `historique-service` sans conflit.**

> Chaque application Spring Boot s'exécute dans son propre processus JVM et écoute sur un **port TCP distinct** (8761 pour Eureka, 8081 et 8083 pour `calcul-service`, 8082 pour `historique-service`, 8888 pour la passerelle). Un conflit de port (`BindException`) ne survient que si deux processus tentent d'écouter sur le même port de la même interface réseau en même temps.

---

## 📌 Partie C : Enregistrement des Microservices

### Question C.1
**Les deux instances portent le même nom `CALCUL-SERVICE` mais des identifiants différents. À quoi sert chacune de ces deux informations pour un microservice qui veut appeler `calcul-service` ?**

> - Le **nom de service** (`CALCUL-SERVICE`) sert de **nom logique de service** aux appelants (OpenFeign, LoadBalancer, Passerelle) pour cibler le service désiré de façon abstraite, sans connaître son emplacement physique.
> - L'**identifiant d'instance** (`calcul-service:8081`, `calcul-service:8083`) identifie de manière **unique chaque exemplaire physique** dans Eureka pour suivre son cycle de vie (battements de cœur) et permettre au LoadBalancer de router précisément vers une instance précise.

---

### Question C.2
**Que se passerait-il si l'on lançait la seconde instance sans l'option `--server.port=8083` ?**

> Sans cette option de surcharge, la seconde instance lirait le port configuré par défaut dans `application.properties` (`8081`). Comme la première instance occupe déjà ce port, le démarrage échouerait immédiatement avec l'erreur :  
> `java.net.BindException: Address already in use: bind` (*Web server failed to start. Port 8081 was already in use*).

---

## 📌 Partie D : Appels Déclaratifs avec OpenFeign

### Tableau D.4 : Tests Directs sur `historique-service` (Port 8082)

| N° | Méthode & URI | Corps de Requête Envoyé | Statut HTTP | En-tête Location / Corps de Réponse Obtenu | Instance de `calcul-service` ayant tracé |
|:--:|:---|:---|:--:|:---|:--:|
| **1** | `POST /operations` | `{"operateur":"somme","a":8,"b":2}` | **201 Created** | `Location: http://localhost:8082/operations/1`<br>`{"id":1,"operateur":"somme","a":8,"b":2,"resultat":10.0}` | `[calcul-service:8083]` |
| **2** | `POST /operations` | `{"operateur":"produit","a":6,"b":7}` | **201 Created** | `Location: http://localhost:8082/operations/2`<br>`{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0}` | `[calcul-service:8081]` |
| **3** | `POST /operations` | `{"operateur":"division","a":7,"b":2}` | **201 Created** | `Location: http://localhost:8082/operations/3`<br>`{"id":3,"operateur":"division","a":7,"b":2,"resultat":3.5}` | `[calcul-service:8083]` |
| **4** | `POST /operations` | `{"operateur":"division","a":7,"b":0}` | **400 Bad Request** | `{"erreur":"Erreur : division par 0 impossible"}` | `[calcul-service:8081]` |
| **5** | `POST /operations` | `{"operateur":"racine","a":9,"b":0}` | **400 Bad Request** | `{"erreur":"Operateur inconnu : racine"}` | *(Aucun appel — rejet local)* |
| **6** | `GET /operations` | *(aucun)* | **200 OK** | `[{"id":1,"operateur":"somme","a":8,"b":2,"resultat":10.0},{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0},{"id":3,"operateur":"division","a":7,"b":2,"resultat":3.5}]` | *(Lecture locale en mémoire)* |
| **7** | `GET /operations/2` | *(aucun)* | **200 OK** | `{"id":2,"operateur":"produit","a":6,"b":7,"resultat":42.0}` | *(Lecture locale en mémoire)* |

---

### Question D.1
**Renvoyez six fois la requête 1 et notez, pour chacune, l'instance qui a affiché la trace. Quelle est la règle de choix ? Comment s'appelle cette stratégie ?**

> - **Traces observées lors des 6 appels consécutifs :**
>   1. Requête 1 $\rightarrow$ `[calcul-service:8083] somme 8+2`
>   2. Requête 2 $\rightarrow$ `[calcul-service:8081] somme 8+2`
>   3. Requête 3 $\rightarrow$ `[calcul-service:8083] somme 8+2`
>   4. Requête 4 $\rightarrow$ `[calcul-service:8081] somme 8+2`
>   5. Requête 5 $\rightarrow$ `[calcul-service:8083] somme 8+2`
>   6. Requête 6 $\rightarrow$ `[calcul-service:8081] somme 8+2`
> - **Règle de choix :** Les requêtes sont transmises successivement d'une instance à l'autre en boucle circulaire fermée.
> - **Nom de la stratégie :** La stratégie de répartition de charge par **tour de rôle (*Round-Robin*)**.

---

### Question D.2
**Dans CalculClient, remplacez `name = "CALCUL-SERVICE"` par `name = "CALCUL-SERVIC"` (faute volontaire), relancez `historique-service` et renvoyez la requête 1. Quel statut obtenez-vous, et par quel bloc catch la réponse est-elle produite ? Remettez ensuite le bon nom.**

> - **Statut obtenu :** **`503 Service Unavailable`** avec le corps JSON :
>   ```json
>   {"erreur": "calcul-service injoignable"}
>   ```
> - **Bloc catch producteur :** La réponse est produite par le bloc générique `catch (FeignException e)`. Ne trouvant aucune instance active associée au nom erroné `CALCUL-SERVIC` dans sa copie locale de l'annuaire Eureka, le répartiteur *Spring Cloud LoadBalancer* échoue et Feign lève une `FeignException` (sous-type `ServiceUnavailable`).

---

## 📌 Partie E : La Passerelle Gateway

### Tableau E.2 : Tests des Routes Statiques en YAML via la Passerelle (Port 8888)

| N° | Requête Vue Client (`:8888`) | Statut HTTP | Réponse Obtenue | Composant ayant répondu |
|:--:|:---|:--:|:---|:---|
| **1** | `GET /calcul/somme?a=2&b=3` | **200 OK** | `5` | `calcul-service 8081` (trace `[calcul-service:8081] somme 2+3`) |
| **2** | `GET /calcul/division?a=7&b=0` | **400 Bad Request** | `Erreur : division par 0 impossible` | `calcul-service 8081` |
| **3** | `GET /operations` | **200 OK** | Tableau JSON des opérations créées en D.4 | `historique-service` |
| **4** | `POST /operations`<br>`{"operateur":"soustraction","a":10,"b":4}` | **201 Created** | `{"id":4,"operateur":"soustraction","a":10,"b":4,"resultat":6.0}`<br>En-tête Location : `http://localhost:8888/operations/4` | `historique-service`, puis une instance de `calcul-service` |
| **5** | `GET /calcul/somme/detail?a=2&b=3` | **200 OK** | `{"operation":"somme","a":2,"b":3,"resultat":5.0}` | `calcul-service 8081` |
| **6** | `GET /bonjour` *(navigateur)* | **404 Not Found** | Corps JSON d'erreur 404 de la passerelle | **La passerelle elle-même** (aucune route ne correspond) |

---

### Question E.1
**Dans la requête 4, l'en-tête Location indique le port 8888 et non 8082, alors que c'est `historique-service` qui l'a construit avec `ServletUriComponentsBuilder.fromCurrentRequest()`. Expliquez comment la passerelle a pu obtenir ce résultat (indication : regardez les en-têtes X-Forwarded-* de la requête reçue par `historique-service`).**

> Lors du transfert de la requête, la passerelle Spring Cloud Gateway injecte les en-têtes HTTP de relais standard :
> - `X-Forwarded-Host: localhost`
> - `X-Forwarded-Port: 8888`
> - `X-Forwarded-Proto: http`
> 
> Grâce à la directive `server.forward-headers-strategy=framework` dans l'`application.properties` d'`historique-service`, Spring MVC prend en compte ces en-têtes pour reconstruire l'URL publique de la ressource (`http://localhost:8888/operations/4`) telle que vue par le client, au lieu de son adresse interne (`:8082`).

---

### Tableau E.5 : Tests des Routes Dynamiques via la Passerelle (Port 8888)

| N° | Requête Vue Client (`:8888`) | Requête Transmise au Microservice | Statut HTTP | Réponse Obtenue | Composant ayant répondu |
|:--:|:---|:---|:--:|:---|:---|
| **1** | `GET /calcul-service/calcul/somme?a=2&b=3` | `GET /calcul/somme?a=2&b=3` | **200 OK** | `5` | `calcul-service:8081` |
| **2** | `GET /calcul-service/calcul/produit/6/7` | `GET /calcul/produit/6/7` | **200 OK** | `42` | `calcul-service:8083` |
| **3** | `GET /historique-service/operations` | `GET /operations` | **200 OK** | Tableau JSON complet des opérations | `historique-service:8082` |
| **4** | `POST /historique-service/operations`<br>`{"operateur":"somme","a":1,"b":1}` | `POST /operations` | **201 Created** | `{"id":5,"operateur":"somme","a":1,"b":1,"resultat":2.0}` | `historique-service` puis `calcul-service:8081` |
| **5** | `GET /calcul/somme?a=2&b=3` *(navigateur)* | Aucune *(route statique supprimée)* | **404 Not Found** | Corps JSON d'erreur de la passerelle | La passerelle elle-même |
| **6** | `GET /gateway-service/actuator/gateway/routes` | `GET /actuator/gateway/routes` | **200 OK** | Liste JSON des routes dynamiques actives | La passerelle elle-même |

---

### Question E.2
**Comparez les URI des étapes E.3 et E.5 pour une même requête. Quel est l'avantage de chaque forme ? Laquelle oblige à modifier la passerelle quand on ajoute un microservice ?**

> - **Forme statique (étape E.3 : `/calcul/...`, `/operations/...`) :**
>   - *Avantage :* URI plus concises et masquant le nom technique interne du microservice.
>   - *Inconvénient :* **Oblige à modifier la passerelle** (fichier YAML ou code Java) chaque fois qu'un nouveau microservice est ajouté.
> - **Forme dynamique (étape E.5 : `/calcul-service/calcul/...`, `/historique-service/operations/...`) :**
>   - *Avantage :* **Découverte automatique sans aucune maintenance** : chaque service enregistré dans Eureka se voit automatiquement attribuer sa route sans toucher à la configuration de la passerelle.
>   - *Inconvénient :* URI plus longues qui exposent le nom technique du service en premier segment.

---

### Question E.3
**La route 6 du tableau montre que la passerelle a une route vers elle-même. Pourquoi ? Est-ce gênant ?**

> - **Pourquoi :** `gateway-service` s'enregistre lui-même dans l'annuaire Eureka sous le nom `GATEWAY-SERVICE`. Le mécanisme `discovery.locator.enabled: true` créant systématiquement une route pour chaque service listé dans Eureka, il crée la route `/gateway-service/**` vers `lb://GATEWAY-SERVICE` (c'est-à-dire vers la passerelle elle-même).
> - **Est-ce gênant :** Oui, car cela permet des appels récursifs inutiles (`/gateway-service/gateway-service/...`) pouvant provoquer des boucles de routage et saturer les ressources du serveur. En production, on désactive cette route en filtrant `GATEWAY-SERVICE` dans la configuration du locator.

---

## 📌 Questions de Synthèse

### 1. Reprise du Tableau A.3 et Étapes d'Observation
| Aspect | TP3 | TP4 (Spring Cloud) | Étape d'Observation |
|:---|:---|:---|:---:|
| **Dépendances Maven** | `spring-boot-starter-webmvc` | Starters Eureka (Client/Server), OpenFeign, Gateway WebFlux, springdoc, Lombok | **B.1, C.1, C.7, E.1** |
| **Adresse d'un microservice** | Codée en dur : `http://localhost:8081` | Résolue par nom logique : `CALCUL-SERVICE` via Eureka | **D.2, E.3** |
| **Appel entre microservices** | Classe `CalculClient` avec `RestClient` | Interface déclarative `CalculClient` annotée `@FeignClient` | **D.2, D.3** |
| **Erreurs d'appel** | `HttpClientErrorException`, `ResourceAccessException` | `FeignException.BadRequest`, `FeignException` | **D.3, D.4** |
| **Point d'entrée du client** | Un port par microservice (`8081`, `8082`) | Un seul port : la passerelle `8888` | **E.2, E.3, E.5** |
| **Plusieurs instances d'un service** | Possible, mais inutilisées | Enregistrées dans Eureka, sollicitées en Round-Robin | **C.5, D.1, D.4, E.3** |
| **Serveur embarqué** | Tomcat (bloquant) partout | Tomcat pour microservices, Netty (non bloquant réactif) pour la Gateway | **B.5, E.2** |
| **Arrêt d'un microservice** | Échec immédiat (503) | Les autres instances prennent le relais (*failover*) ; 503 si plus aucune | **C.6** |
| **Organisation du code** | Deux projets séparés | Projet multi-modules Maven (`calculatrice-spring-cloud`) | **B.0, C.0, E.1** |
| **Outil de test** | curl, Postman | Interface Swagger UI centralisée sur chaque service et sur la passerelle | **C.4, D.4, E.2** |
| **Classes de données** | Constructeurs, getters, setters écrits à la main | Générés automatiquement à la compilation par Lombok | **C.1 bis, C.7** |

---

### 2. Trajet Complet de la Requête `POST :8888/historique-service/operations`
*Corps de la requête :* `{"operateur":"somme","a":1,"b":2}`

```
Client                  Passerelle (8888)            Eureka (8761)        Historique (8082)         Calcul (8081)
  |                             |                          |                      |                       |
  | 1. POST /historique-service |                          |                      |                       |
  |    /operations              |                          |                      |                       |
  |---------------------------->|                          |                      |                       |
  |                             | 2. Consulte annuaire     |                      |                       |
  |                             |    (HISTORIQUE-SERVICE)  |                      |                       |
  |                             |------------------------->|                      |                       |
  |                             |<-------------------------|                      |                       |
  |                             |                          |                      |                       |
  |                             | 3. Réécrit en /operations|                      |                       |
  |                             |    et relaie HTTP POST   |                      |                       |
  |                             |------------------------------------------------>|                       |
  |                             |                          |                      | 4. Traite la requête  |
  |                             |                          |                      |    Appelle Feign      |
  |                             |                          |                      |    calculClient       |
  |                             |                          | 5. LoadBalancer      |                       |
  |                             |                          |    résout instance   |                       |
  |                             |                          |    CALCUL-SERVICE    |                       |
  |                             |                          |<---------------------|                       |
  |                             |                          |    Retourne 8081     |                       |
  |                             |                          |--------------------->|                       |
  |                             |                          |                      | 6. HTTP GET           |
  |                             |                          |                      |    /calcul/somme?a=1&b=2
  |                             |                          |                      |---------------------->|
  |                             |                          |                      |                       | 7. Calcule 1+2
  |                             |                          |                      |                       |    Trace: [8081]
  |                             |                          |                      | 8. Réponse text: "3"  |
  |                             |                          |                      |<----------------------|
  |                             |                          |                      | 9. Parse double (3.0) |
  |                             |                          |                      |    Enregistre en mémoire
  |                             | 10. HTTP 201 Created     |                      |    Location: :8888... |
  |                             |     + JSON opération     |                      |                       |
  |                             |<------------------------------------------------|                       |
  | 11. Relaye HTTP 201         |                          |                      |                       |
  |<----------------------------|                          |                      |                       |
```

---

### 3. Répartiteur de Charge Spring Cloud LoadBalancer
Dans ce TP, trois programmes intègrent *Spring Cloud LoadBalancer* :
1. **`historique-service` :** Résout le nom logique de service **`CALCUL-SERVICE`** pour répartir les calculs entre les instances `8081` et `8083`.
2. **`gateway-service` :** Résout les noms logiques **`CALCUL-SERVICE`** et **`HISTORIQUE-SERVICE`** pour router les requêtes reçues vers les instances appropriées.
3. **`calcul-service` :** Inclut la dépendance (apportée transitivement par le client Eureka), mais ne résout **aucun nom de service** car il n'effectue aucun appel HTTP sortant vers un autre microservice.

---

### 4. Nécessité des Dépendances selon les Microservices

| Dépendance | `calcul-service` | `historique-service` | `gateway-service` | Justification |
|:---|:---:|:---:|:---:|:---|
| **Eureka Client** | **Oui** | **Oui** | **Oui** | Nécessaire à tous : permet de s'enregistrer auprès de l'annuaire et de découvrir les autres services enregistrés. |
| **OpenFeign** | **Non** | **Oui** | **Non** | Nécessaire uniquement à `historique-service` pour consommer déclarativement l'API de `calcul-service`. La passerelle n'en a pas besoin car elle réalise un routage HTTP réseau réactif direct. |
| **Spring Cloud Gateway** | **Non** | **Non** | **Oui** | Nécessaire uniquement à `gateway-service` : c'est le moteur de routage réactif non bloquant fondé sur WebFlux et Netty. |

---

### 5. Résolution du Problème de l'Adresse en Dur
Dans le TP3, l'adresse de `calcul-service` était codée en dur dans `application.properties` (`calcul.service.url=http://localhost:8081`), ce qui empêchait tout passage à l'échelle horizontale et toute tolérance aux pannes.

Dans ce TP4, ce problème est complètement résolu grâce à trois briques Spring Cloud :
1. **Eureka Server & Client :** Enregistre dynamiquement toutes les instances actives avec leur adresse IP et port réels.
2. **Spring Cloud LoadBalancer :** Détecte la liste des instances disponibles pour `CALCUL-SERVICE` et équilibre automatiquement la charge en *Round-Robin*.
3. **OpenFeign :** Remplace l'URL fixe par le nom abstrait du service (`@FeignClient(name = "CALCUL-SERVICE")`), rendant l'appelant totalement agnostique de l'adresse physique du fournisseur.

---

### 6. Microservice Stateless vs Stockage en Mémoire
- **Comportement observé :** Si deux instances d'`historique-service` tournent sur les ports 8082 et 8084, la passerelle répartit les 3 requêtes `POST` entre les deux instances. Une requête ultérieure `GET /historique-service/operations` ne renverra que les opérations stockées localement par l'instance qui reçoit la requête (par exemple 2 opérations sur une instance, 1 opération sur l'autre), donnant une vue incomplète et incohérente.
- **Principe violé :** Le principe de **microservice sans état (*stateless*)**. L'état d'un service ne doit jamais être conservé dans la mémoire vive locale d'un processus.
- **Correction :** Remplacer la liste en mémoire par un stockage externe partagé : une **base de données relationnelle centralisée** (ex: PostgreSQL, MySQL) ou un **cache distribué partagé** (ex: Redis), rendant toutes les instances d'`historique-service` strictement interchangeables.

---

### 7. Commandes de Construction et d'Exécution sans IDE
1. **Compilation et empaquetage de l'ensemble des modules en une commande à la racine :**
   ```bash
   cd calculatrice-spring-cloud
   mvn clean package -DskipTests
   ```

2. **Démarrage des 5 programmes dans l'ordre strict :**
   ```bash
   # 1. Annuaire Eureka (toujours en premier)
   java -jar eureka-service/target/eureka-service-0.0.1-SNAPSHOT.jar

   # 2. Instance 1 de calcul-service (port par défaut 8081)
   java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar

   # 3. Instance 2 de calcul-service (port surchargé 8083)
   java -jar calcul-service/target/calcul-service-0.0.1-SNAPSHOT.jar --server.port=8083

   # 4. Microservice historique-service (port 8082)
   java -jar historique-service/target/historique-service-0.0.1-SNAPSHOT.jar

   # 5. Passerelle Gateway (toujours en dernier)
   java -jar gateway-service/target/gateway-service-0.0.1-SNAPSHOT.jar
   ```

---

### 8. Rôle de `@GetMapping("/calcul/{operateur}")` : Serveur vs Client
- **Dans `CalculController` (Côté Serveur / Implémentation) :**  
  Configure un **point de terminaison entrant**. Elle ordonne au conteneur Spring de réceptionner les requêtes HTTP `GET` correspondant à ce chemin, de lier les paramètres de la requête aux arguments de la méthode Java et d'exécuter le calcul.
- **Dans `CalculClient` (Côté Client / Contrat OpenFeign) :**  
  Sert de **modèle de requête sortante**. OpenFeign analyse cette métadonnée pour générer dynamiquement l'implémentation Java qui assemble et envoie une requête HTTP `GET` réelle vers l'adresse de l'instance sélectionnée par le LoadBalancer.

---

### 9. Multi-Modules Maven vs Indépendance des Microservices
Le regroupement sous un projet multi-modules Maven **ne remet aucunement en cause l'indépendance des microservices** :
- **JVM distinctes :** Chaque microservice s'exécute dans un processus JVM totalement séparé.
- **Ports distincts :** Chaque service écoute sur son propre port réseau (8761, 8081, 8083, 8082, 8888).
- **Fichiers JAR autonomes :** La commande Maven génère des fichiers `.jar` auto-contenus et indépendants.
- **Cycle de vie autonome :** Chaque microservice peut être démarré, arrêté, mis à jour et redéployé individuellement sans interrompre les autres (comme démontré lors de l'arrêt de l'instance 8083 en partie C.6).

---

### 10. Origine de l'Adresse dans Swagger UI et Rôle de `server.forward-headers-strategy`
- **Origine de l'adresse :** Elle provient des en-têtes HTTP de relais injectés par la passerelle (`X-Forwarded-Host: localhost`, `X-Forwarded-Port: 8888` et `X-Forwarded-Prefix`).
- **Conséquence sans `server.forward-headers-strategy=framework` :**  
  Le microservice ignorerait ces en-têtes et renverrait son adresse locale interne (`http://localhost:8081` ou `:8082`). Lors d'un clic sur *Execute* dans Swagger UI, le navigateur enverrait la requête directement au microservice au lieu de traverser la passerelle, cassant l'architecture de sécurité (point d'entrée unique), provoquant des erreurs CORS et rendant l'API inutilisable si les microservices se trouvent sur un réseau privé inaccessible au client.

---

### 11. Fonctionnement de Lombok et Exclusion du JAR Exécutable
- **Où se trouvent les méthodes générées :**  
  Lombok s'exécute lors de la compilation (`javac`) via son *Annotation Processor*. Il injecte directement les constructeurs, getters, setters et méthodes `toString` sous forme de **byte-code natif dans les fichiers `.class`** (visible dans `target/classes/com/exemple/historique/model/Operation.class`).
- **Pourquoi Lombok peut être exclu du JAR :**  
  Une fois la compilation terminée, le byte-code contient déjà l'ensemble des méthodes compilées. La bibliothèque Lombok n'a plus aucune utilité lors de l'exécution (*runtime*). Son exclusion via la balise `<excludes>` du plugin Maven allège le `.jar` final sans impacter l'application.
