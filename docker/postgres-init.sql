-- Retail OLTP seed schema for the apprentice demo.
-- Loaded by the postgres-oltp container at first start.

CREATE TABLE IF NOT EXISTS public.clients (
    id            BIGSERIAL PRIMARY KEY,
    full_name     VARCHAR(200) NOT NULL,
    email         VARCHAR(160) NOT NULL,
    segment_code  VARCHAR(20),
    city          VARCHAR(100),
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.products (
    id             BIGSERIAL PRIMARY KEY,
    name           VARCHAR(200) NOT NULL,
    category_code  VARCHAR(80),
    brand          VARCHAR(80),
    price          NUMERIC(18, 2),
    created_at     TIMESTAMP NOT NULL DEFAULT now(),
    updated_at     TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.orders (
    id            BIGSERIAL PRIMARY KEY,
    client_id     BIGINT NOT NULL REFERENCES public.clients (id),
    order_ts      TIMESTAMP NOT NULL,
    status        VARCHAR(20) NOT NULL,
    channel       VARCHAR(20),
    total_amount  NUMERIC(18, 2),
    created_at    TIMESTAMP NOT NULL DEFAULT now(),
    updated_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_orders_updated_at ON public.orders (updated_at);
CREATE INDEX IF NOT EXISTS ix_clients_updated_at ON public.clients (updated_at);

-- Minimal seed: 5 clients, 4 products, 8 orders.
INSERT INTO public.clients (full_name, email, segment_code, city) VALUES
  ('Иван Иванов',     'ivan@example.com',  'A', 'Москва'),
  ('Пётр Петров',     'petr@example.com',  'B', 'Санкт-Петербург'),
  ('Анна Сидорова',   'anna@example.com',  'A', 'Казань'),
  ('Олег Кузнецов',   'oleg@example.com',  'C', 'Екатеринбург'),
  ('Мария Соколова',  'maria@example.com', 'B', 'Новосибирск')
ON CONFLICT DO NOTHING;

INSERT INTO public.products (name, category_code, brand, price) VALUES
  ('Coffee Maker',  'KITCHEN', 'Bosch',    12990.00),
  ('Headphones',    'AUDIO',   'Sony',      9990.00),
  ('Vacuum',        'KITCHEN', 'Dyson',    49990.00),
  ('Smartwatch',    'WEARABLE','Garmin',   29990.00)
ON CONFLICT DO NOTHING;

INSERT INTO public.orders (client_id, order_ts, status, channel, total_amount) VALUES
  (1, now() - interval '7 days',  'paid',     'web',    12990.00),
  (1, now() - interval '5 days',  'paid',     'mobile',  9990.00),
  (2, now() - interval '4 days',  'shipped',  'web',    49990.00),
  (3, now() - interval '3 days',  'paid',     'web',    29990.00),
  (4, now() - interval '2 days',  'cancelled','mobile',     0.00),
  (5, now() - interval '1 day',   'paid',     'web',     9990.00),
  (1, now() - interval '12 hours','paid',     'mobile', 12990.00),
  (3, now() - interval '6 hours', 'paid',     'web',    49990.00)
ON CONFLICT DO NOTHING;
