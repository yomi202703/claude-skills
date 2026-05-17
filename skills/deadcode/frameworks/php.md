# PHP

## LENSES

Output schema: `[{file, line, name, kind, lens, safety}]`.

### L1 — shipmonk dead-code-detector (safety: 3)

```
vendor/bin/dead-code-detector --format=json \
  | jq '[.findings // [] | .[] | {file, line, name: (.member // .className), kind: (.type // "member"), lens: "shipmonk", safety: 3}]'
```

Install once per project: `composer require --dev shipmonk-rnd/dead-code-detector`.

### L1b — composer-unused (safety: 1, unused composer deps)

```
vendor/bin/composer-unused --output-format=json \
  | jq '[.unused-packages // [] | .[] | {file: "composer.json", line: 0, name: ., kind: "dep", lens: "composer-unused", safety: 1}]'
```

## TEST_CMD

`vendor/bin/phpunit` or `composer test` (check `composer.json` `scripts.test`)
Static check: `vendor/bin/phpstan analyse` / `vendor/bin/psalm`

## FRAMEWORK_HOOKS (skip — treated as live)

### Language magic methods

`__construct` `__destruct` `__call` `__callStatic` `__get` `__set` `__isset` `__unset` `__sleep` `__wakeup` `__serialize` `__unserialize` `__toString` `__invoke` `__set_state` `__clone` `__debugInfo`

### Laravel

- `app/Http/Controllers/**` public methods (referenced from `routes/web.php` / `routes/api.php`)
- `app/Console/Commands/**` `handle()`
- `app/Jobs/**` `handle()`
- `app/Events/**` / `app/Listeners/**`
- `app/Providers/**` `register()` / `boot()`
- Migration class `up()` / `down()`
- Model `$fillable` / `$casts` / `$hidden` / accessors / mutators (`get<X>Attribute` / `set<X>Attribute`)
- Controller@method strings referenced from `routes/*.php`

### Symfony

- Methods under `#[Route('/path')]`
- Classes under `#[AsCommand]`
- Methods under `#[AsEventListener]`
- Classes referenced from `config/services.yaml` service definitions

### Doctrine

- Entity getters/setters (called via metadata)
- Classes under `#[ORM\Entity]`
- Repository class `find*` methods

### Testing

- Test classes referenced from `phpunit.xml`, `test*` methods
- Methods with `@test` annotation
- `setUp` / `tearDown` / `setUpBeforeClass` / `tearDownAfterClass`

### Twig templates

- `*.twig` referenced methods (string-match dispatcher)

## ENTRYPOINTS

- `public/index.php` (web entry)
- `bin/console` (Symfony)
- `artisan` (Laravel)
- `bin` / `scripts` in `composer.json`
