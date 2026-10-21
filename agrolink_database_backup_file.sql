--
-- PostgreSQL database dump
--

-- Dumped from database version 16.2
-- Dumped by pg_dump version 16.2

-- Started on 2026-08-01 21:06:21

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 4930 (class 1262 OID 579293)
-- Name: agrolink_db; Type: DATABASE; Schema: -; Owner: postgres
--

-- CREATE DATABASE agrolink_db WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'English_United States.1252';
-- ALTER DATABASE agrolink_db OWNER TO postgres;
-- \connect agrolink_db

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 854 (class 1247 OID 579300)
-- Name: crop_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.crop_status AS ENUM (
    'growing',
    'ready',
    'harvested'
);


ALTER TYPE public.crop_status OWNER TO postgres;

--
-- TOC entry 857 (class 1247 OID 579308)
-- Name: order_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.order_status AS ENUM (
    'pending',
    'confirmed',
    'delivered',
    'cancelled'
);


ALTER TYPE public.order_status OWNER TO postgres;

--
-- TOC entry 851 (class 1247 OID 579295)
-- Name: user_role; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.user_role AS ENUM (
    'farmer',
    'buyer'
);


ALTER TYPE public.user_role OWNER TO postgres;

--
-- TOC entry 226 (class 1255 OID 579414)
-- Name: update_market_prices_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_market_prices_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_market_prices_updated_at() OWNER TO postgres;

--
-- TOC entry 225 (class 1255 OID 579398)
-- Name: update_orders_updated_at(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_orders_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_orders_updated_at() OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 218 (class 1259 OID 579332)
-- Name: crops; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.crops (
    id integer NOT NULL,
    farmer_id integer NOT NULL,
    crop_name character varying(100) NOT NULL,
    crop_type character varying(50) NOT NULL,
    quantity_kg numeric(10,2) NOT NULL,
    expected_harvest_date date NOT NULL,
    field_location character varying(120),
    notes text,
    status public.crop_status DEFAULT 'growing'::public.crop_status NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT crops_quantity_kg_check CHECK ((quantity_kg > (0)::numeric))
);


ALTER TABLE public.crops OWNER TO postgres;

--
-- TOC entry 4931 (class 0 OID 0)
-- Dependencies: 218
-- Name: TABLE crops; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.crops IS 'Private crop tracking records for farmers.';


--
-- TOC entry 4932 (class 0 OID 0)
-- Dependencies: 218
-- Name: COLUMN crops.farmer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.farmer_id IS 'FK → users.id. Only farmers own crop records.';


--
-- TOC entry 4933 (class 0 OID 0)
-- Dependencies: 218
-- Name: COLUMN crops.quantity_kg; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.quantity_kg IS 'Expected yield in kilograms.';


--
-- TOC entry 4934 (class 0 OID 0)
-- Dependencies: 218
-- Name: COLUMN crops.expected_harvest_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.expected_harvest_date IS 'Planned harvest date for planning purposes.';


--
-- TOC entry 4935 (class 0 OID 0)
-- Dependencies: 218
-- Name: COLUMN crops.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.status IS 'growing → ready → harvested lifecycle.';


--
-- TOC entry 217 (class 1259 OID 579331)
-- Name: crops_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.crops_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.crops_id_seq OWNER TO postgres;

--
-- TOC entry 4936 (class 0 OID 0)
-- Dependencies: 217
-- Name: crops_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.crops_id_seq OWNED BY public.crops.id;


--
-- TOC entry 224 (class 1259 OID 579401)
-- Name: market_prices; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.market_prices (
    id integer NOT NULL,
    crop_name character varying(100) NOT NULL,
    category character varying(50) NOT NULL,
    buying_price numeric(10,2) NOT NULL,
    selling_price numeric(10,2) NOT NULL,
    unit character varying(20) DEFAULT 'per kg'::character varying NOT NULL,
    market_location character varying(100) DEFAULT 'Colombo'::character varying NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT market_prices_buying_price_check CHECK ((buying_price > (0)::numeric)),
    CONSTRAINT market_prices_selling_price_check CHECK ((selling_price > (0)::numeric))
);


ALTER TABLE public.market_prices OWNER TO postgres;

--
-- TOC entry 4937 (class 0 OID 0)
-- Dependencies: 224
-- Name: TABLE market_prices; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.market_prices IS 'Reference market prices for Sri Lankan agricultural products.';


--
-- TOC entry 4938 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN market_prices.buying_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_prices.buying_price IS 'Price farmers receive (LKR per kg).';


--
-- TOC entry 4939 (class 0 OID 0)
-- Dependencies: 224
-- Name: COLUMN market_prices.selling_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_prices.selling_price IS 'Price buyers pay in the open market (LKR per kg).';


--
-- TOC entry 223 (class 1259 OID 579400)
-- Name: market_prices_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.market_prices_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.market_prices_id_seq OWNER TO postgres;

--
-- TOC entry 4940 (class 0 OID 0)
-- Dependencies: 223
-- Name: market_prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.market_prices_id_seq OWNED BY public.market_prices.id;


--
-- TOC entry 222 (class 1259 OID 579372)
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    buyer_id integer NOT NULL,
    product_id integer NOT NULL,
    quantity_kg numeric(10,2) NOT NULL,
    total_price numeric(12,2) NOT NULL,
    status public.order_status DEFAULT 'pending'::public.order_status NOT NULL,
    delivery_address character varying(255),
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT orders_quantity_kg_check CHECK ((quantity_kg > (0)::numeric)),
    CONSTRAINT orders_total_price_check CHECK ((total_price > (0)::numeric))
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- TOC entry 4941 (class 0 OID 0)
-- Dependencies: 222
-- Name: TABLE orders; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.orders IS 'Purchase orders placed by buyers for marketplace products.';


--
-- TOC entry 4942 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN orders.buyer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.buyer_id IS 'FK → users.id. The buyer who placed the order.';


--
-- TOC entry 4943 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN orders.product_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.product_id IS 'FK → products.id. The product being ordered.';


--
-- TOC entry 4944 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN orders.total_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.total_price IS 'Snapshot of quantity_kg × price_per_kg at order time.';


--
-- TOC entry 4945 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN orders.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.status IS 'pending → confirmed → delivered, or cancelled.';


--
-- TOC entry 4946 (class 0 OID 0)
-- Dependencies: 222
-- Name: COLUMN orders.updated_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.updated_at IS 'Auto-updated by trigger on every status change.';


--
-- TOC entry 221 (class 1259 OID 579371)
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orders_id_seq OWNER TO postgres;

--
-- TOC entry 4947 (class 0 OID 0)
-- Dependencies: 221
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- TOC entry 220 (class 1259 OID 579351)
-- Name: products; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.products (
    id integer NOT NULL,
    farmer_id integer NOT NULL,
    name character varying(100) NOT NULL,
    category character varying(50) NOT NULL,
    description text,
    quantity_kg numeric(10,2) NOT NULL,
    price_per_kg numeric(10,2) NOT NULL,
    location character varying(120),
    image_url character varying(255),
    is_available boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT products_price_per_kg_check CHECK ((price_per_kg > (0)::numeric)),
    CONSTRAINT products_quantity_kg_check CHECK ((quantity_kg >= (0)::numeric))
);


ALTER TABLE public.products OWNER TO postgres;

--
-- TOC entry 4948 (class 0 OID 0)
-- Dependencies: 220
-- Name: TABLE products; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.products IS 'Public product listings on the marketplace.';


--
-- TOC entry 4949 (class 0 OID 0)
-- Dependencies: 220
-- Name: COLUMN products.farmer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.farmer_id IS 'FK → users.id. The farmer who listed this product.';


--
-- TOC entry 4950 (class 0 OID 0)
-- Dependencies: 220
-- Name: COLUMN products.quantity_kg; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.quantity_kg IS 'Remaining stock. Decremented when orders are placed.';


--
-- TOC entry 4951 (class 0 OID 0)
-- Dependencies: 220
-- Name: COLUMN products.is_available; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.is_available IS 'FALSE hides the listing without deleting it.';


--
-- TOC entry 219 (class 1259 OID 579350)
-- Name: products_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.products_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.products_id_seq OWNER TO postgres;

--
-- TOC entry 4952 (class 0 OID 0)
-- Dependencies: 219
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
-- TOC entry 216 (class 1259 OID 579318)
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id integer NOT NULL,
    name character varying(120) NOT NULL,
    email character varying(120) NOT NULL,
    password_hash character varying(256) NOT NULL,
    role public.user_role NOT NULL,
    phone character varying(20),
    location character varying(120),
    created_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- TOC entry 4953 (class 0 OID 0)
-- Dependencies: 216
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.users IS 'All registered users — farmers and buyers.';


--
-- TOC entry 4954 (class 0 OID 0)
-- Dependencies: 216
-- Name: COLUMN users.id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.id IS 'Auto-incrementing primary key.';


--
-- TOC entry 4955 (class 0 OID 0)
-- Dependencies: 216
-- Name: COLUMN users.email; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.email IS 'Unique login email address.';


--
-- TOC entry 4956 (class 0 OID 0)
-- Dependencies: 216
-- Name: COLUMN users.password_hash; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.password_hash IS 'Werkzeug pbkdf2 password hash — never store plain text.';


--
-- TOC entry 4957 (class 0 OID 0)
-- Dependencies: 216
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.role IS 'farmer = can list products & manage crops; buyer = can place orders.';


--
-- TOC entry 215 (class 1259 OID 579317)
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO postgres;

--
-- TOC entry 4958 (class 0 OID 0)
-- Dependencies: 215
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- TOC entry 4721 (class 2604 OID 579335)
-- Name: crops id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops ALTER COLUMN id SET DEFAULT nextval('public.crops_id_seq'::regclass);


--
-- TOC entry 4731 (class 2604 OID 579404)
-- Name: market_prices id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_prices ALTER COLUMN id SET DEFAULT nextval('public.market_prices_id_seq'::regclass);


--
-- TOC entry 4727 (class 2604 OID 579375)
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- TOC entry 4724 (class 2604 OID 579354)
-- Name: products id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- TOC entry 4719 (class 2604 OID 579321)
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- TOC entry 4918 (class 0 OID 579332)
-- Dependencies: 218
-- Data for Name: crops; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.crops VALUES (1, 1, 'Tomato', 'Vegetables', 500.00, '2025-03-15', 'North Field, Kandy', NULL, 'growing', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.crops VALUES (2, 1, 'Carrot', 'Vegetables', 300.00, '2025-04-01', 'East Field, Kandy', NULL, 'growing', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.crops VALUES (3, 1, 'Ginger', 'Spices', 150.00, '2025-05-20', 'South Field, Kandy', NULL, 'ready', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.crops VALUES (4, 2, 'Maize', 'Grains & Rice', 800.00, '2025-03-30', 'Main Field, Matale', NULL, 'growing', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.crops VALUES (5, 2, 'Cabbage', 'Vegetables', 400.00, '2025-03-10', 'Lower Field, Matale', NULL, 'ready', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.crops VALUES (6, 4, 'Tomato', 'Vegetables', 2.00, '2026-04-11', 'kandy', 'fresh food', 'ready', '2026-04-11 12:24:37.228013') ON CONFLICT DO NOTHING;


--
-- TOC entry 4924 (class 0 OID 579401)
-- Dependencies: 224
-- Data for Name: market_prices; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.market_prices VALUES (1, 'Tomato', 'Vegetables', 85.00, 120.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (2, 'Carrot', 'Vegetables', 60.00, 95.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (3, 'Cabbage', 'Vegetables', 45.00, 75.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (4, 'Beans', 'Vegetables', 110.00, 160.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (5, 'Brinjal', 'Vegetables', 70.00, 105.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (6, 'Leeks', 'Vegetables', 130.00, 180.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (7, 'Pumpkin', 'Vegetables', 40.00, 65.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (8, 'Cucumber', 'Vegetables', 55.00, 85.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (9, 'Banana', 'Fruits', 65.00, 100.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (10, 'Mango', 'Fruits', 120.00, 180.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (11, 'Pineapple', 'Fruits', 80.00, 130.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (12, 'Papaya', 'Fruits', 55.00, 90.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (13, 'Avocado', 'Fruits', 150.00, 220.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (14, 'Rice (Samba)', 'Grains & Rice', 95.00, 135.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (15, 'Rice (Nadu)', 'Grains & Rice', 85.00, 120.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (16, 'Maize', 'Grains & Rice', 55.00, 80.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (17, 'Red Chilli', 'Spices', 700.00, 950.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (18, 'Turmeric', 'Spices', 450.00, 650.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (19, 'Ginger', 'Spices', 300.00, 480.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (20, 'Garlic', 'Spices', 350.00, 520.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (21, 'Lentils', 'Pulses', 170.00, 240.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (22, 'Chickpeas', 'Pulses', 190.00, 270.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (23, 'Sweet Potato', 'Roots & Tubers', 70.00, 110.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (24, 'Cassava', 'Roots & Tubers', 40.00, 65.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.market_prices VALUES (25, 'Potato', 'Roots & Tubers', 80.00, 120.00, 'per kg', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;


--
-- TOC entry 4922 (class 0 OID 579372)
-- Dependencies: 222
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.orders VALUES (1, 3, 1, 10.00, 1150.00, 'pending', 'No. 45, Galle Road, Colombo 03', NULL, '2026-04-11 17:25:04.493704', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.orders VALUES (2, 5, 3, 1.00, 60.00, 'pending', 'MOratuwa', 'Hoda ewa ewanna', '2026-04-11 13:00:08.075652', '2026-04-11 13:00:08.075662') ON CONFLICT DO NOTHING;
INSERT INTO public.orders VALUES (3, 5, 4, 1.00, 450.00, 'delivered', 'mnnnm', 'hjgjhbkjhb', '2026-04-11 13:02:55.507835', '2026-04-11 18:33:40.141054') ON CONFLICT DO NOTHING;
INSERT INTO public.orders VALUES (4, 7, 3, 3.00, 180.00, 'pending', '123 asdfgj', 'good vegitebel need', '2026-05-16 12:01:42.943583', '2026-05-16 12:01:42.943592') ON CONFLICT DO NOTHING;
INSERT INTO public.orders VALUES (5, 8, 3, 2.00, 120.00, 'pending', 'shoun123', 'good vegitabel', '2026-05-16 12:05:12.063102', '2026-05-16 12:05:12.063111') ON CONFLICT DO NOTHING;
INSERT INTO public.orders VALUES (6, 8, 5, 20.00, 3800.00, 'delivered', '123 apanadura', 'thank you', '2026-05-16 12:10:44.357296', '2026-05-16 17:41:58.616373') ON CONFLICT DO NOTHING;


--
-- TOC entry 4920 (class 0 OID 579351)
-- Dependencies: 220
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.products VALUES (1, 1, 'Fresh Tomatoes', 'Vegetables', 'Organically grown, vine-ripened tomatoes. No pesticides used.', 200.00, 115.00, 'Kandy', 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400&q=80', true, '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.products VALUES (2, 1, 'Fresh Ginger', 'Spices', 'Sun-dried premium quality ginger from hill country farms.', 80.00, 420.00, 'Kandy', 'https://images.unsplash.com/photo-1506368249639-73a05d6f6488?w=400&q=80', true, '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.products VALUES (4, 4, 'Tomatoes adfh', 'Vegetables', 'Apen witharai hoda badu', 1.00, 450.00, 'nuwar eliya', 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400&q=80', true, '2026-04-11 12:26:42.570777') ON CONFLICT DO NOTHING;
INSERT INTO public.products VALUES (3, 2, 'Fresh Cabbage', 'Vegetables', 'Crisp and fresh cabbages, harvested this week.', 144.00, 60.00, 'Matale', 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400&q=80', true, '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.products VALUES (5, 9, 'carret', 'Vegetables', 'good', 180.00, 190.00, 'panadura', 'https://images.unsplash.com/photo-1540420773420-3366772f4999?w=400&q=80', true, '2026-05-16 12:08:28.050677') ON CONFLICT DO NOTHING;


--
-- TOC entry 4916 (class 0 OID 579318)
-- Dependencies: 216
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

INSERT INTO public.users VALUES (1, 'Nimal Perera', 'nimal@agrolink.lk', 'scrypt:32768:8:1$hh1C3aIHnUWRkBKZ$3ccba2365015481b5211f64e16be21bd4593877aa45d78e85f37dd9583f9e0f46694c2a3bf2646633535eeb62f16322202df719c6608551a5e63eaca64438853', 'farmer', '+94771234567', 'Kandy', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (2, 'Sunil Fernando', 'sunil@agrolink.lk', 'scrypt:32768:8:1$hh1C3aIHnUWRkBKZ$3ccba2365015481b5211f64e16be21bd4593877aa45d78e85f37dd9583f9e0f46694c2a3bf2646633535eeb62f16322202df719c6608551a5e63eaca64438853', 'farmer', '+94779876543', 'Matale', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (3, 'Kamani Silva', 'kamani@agrolink.lk', 'scrypt:32768:8:1$hh1C3aIHnUWRkBKZ$3ccba2365015481b5211f64e16be21bd4593877aa45d78e85f37dd9583f9e0f46694c2a3bf2646633535eeb62f16322202df719c6608551a5e63eaca64438853', 'buyer', '+94712345678', 'Colombo', '2026-04-11 17:25:04.493704') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (4, 'hashan mart', 'hashanmart123@gmail.com', 'scrypt:32768:8:1$GBl14xf08jZxjqZF$a6c9ad063246d58a8dc6ff0e16c019eb4755b77f3e9e928f90ce1cec20b72ab5b87262ce850ac3cc02beb08531364041f30f110e0d4c950185edf2fd2424ec6e', 'farmer', '94766720164', 'nuwar eliya', '2026-04-11 12:13:53.467061') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (5, 'jiwantha pvt ltd', 'jiwanthapvt@gmail.com', 'scrypt:32768:8:1$uAcu6aldB0ooMK4H$80f349aefef64ccdd714fc03c7bff6513c0799495c225ce8b40444172e257eb93ea1e294303828c2b7f115f7a255b753a2ae464df30c54d29cbc5391c0470c64', 'buyer', '0112365365', 'colombo', '2026-04-11 12:19:51.141194') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (6, 'Sahasra Kesara', 'sahasrakesara@gmail.com', 'scrypt:32768:8:1$9DOLlUc9TF19kim5$90af6faabc30cf5c06f28fd4c6ceae8180759bb75ffab6b2e76222de615bc32b1467137c0d72fb34d659b8d1e4796e785478a5c2c2ae24915008a0310e41a6da', 'farmer', '', '', '2026-05-16 11:37:00.388377') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (7, 'Kesara', 'kesara@gmail.com', 'scrypt:32768:8:1$xNM3B2SmuqProimQ$a6a26414b2e0473aa99cd136bf3a1b334839227f0c81c494a5cac95fd7fcb99fd9c3ff6b0e585ee1b9f8d4b1876daf9746886379b40afb47e2e84fefad67b3bf', 'buyer', '+94770568688', '', '2026-05-16 11:48:13.976254') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (8, 'shoun', 'shoun@sdnf', 'scrypt:32768:8:1$XQ8W9bGsFEkZZSlZ$651a1ec5e863aef00910b00b976af84a917b3110bf15847589d99013f3363a3acb2096c819df9564e9c6b61ffaf84638af08f0684f0bfe85e2e4e3bd1c0b1f25', 'buyer', '', '', '2026-05-16 12:04:12.610011') ON CONFLICT DO NOTHING;
INSERT INTO public.users VALUES (9, 'shoun', 'shoun@fas', 'scrypt:32768:8:1$rtFCJR5HqRH8nVTn$80044a27e5454c1c5985d1c5169dfb28d80d09b5861e5c9cd87d86344db05fe4a1d2bd3399485efc9a66f62566b8ad114551d31e9951f0c8cce4dede2488c66a', 'farmer', '', '', '2026-05-16 12:06:13.461462') ON CONFLICT DO NOTHING;


--
-- TOC entry 4959 (class 0 OID 0)
-- Dependencies: 217
-- Name: crops_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.crops_id_seq', 6, true);


--
-- TOC entry 4960 (class 0 OID 0)
-- Dependencies: 223
-- Name: market_prices_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.market_prices_id_seq', 25, true);


--
-- TOC entry 4961 (class 0 OID 0)
-- Dependencies: 221
-- Name: orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.orders_id_seq', 6, true);


--
-- TOC entry 4962 (class 0 OID 0)
-- Dependencies: 219
-- Name: products_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.products_id_seq', 5, true);


--
-- TOC entry 4963 (class 0 OID 0)
-- Dependencies: 215
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 9, true);


--
-- TOC entry 4749 (class 2606 OID 579342)
-- Name: crops crops_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_pkey PRIMARY KEY (id);


--
-- TOC entry 4765 (class 2606 OID 579411)
-- Name: market_prices market_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_prices
    ADD CONSTRAINT market_prices_pkey PRIMARY KEY (id);


--
-- TOC entry 4761 (class 2606 OID 579384)
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- TOC entry 4756 (class 2606 OID 579362)
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- TOC entry 4745 (class 2606 OID 579328)
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- TOC entry 4747 (class 2606 OID 579326)
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- TOC entry 4750 (class 1259 OID 579348)
-- Name: idx_crops_farmer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crops_farmer_id ON public.crops USING btree (farmer_id);


--
-- TOC entry 4751 (class 1259 OID 579349)
-- Name: idx_crops_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crops_status ON public.crops USING btree (status);


--
-- TOC entry 4762 (class 1259 OID 579412)
-- Name: idx_market_prices_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_prices_category ON public.market_prices USING btree (category);


--
-- TOC entry 4763 (class 1259 OID 579413)
-- Name: idx_market_prices_crop; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_prices_crop ON public.market_prices USING btree (crop_name);


--
-- TOC entry 4757 (class 1259 OID 579395)
-- Name: idx_orders_buyer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_buyer_id ON public.orders USING btree (buyer_id);


--
-- TOC entry 4758 (class 1259 OID 579396)
-- Name: idx_orders_product_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_product_id ON public.orders USING btree (product_id);


--
-- TOC entry 4759 (class 1259 OID 579397)
-- Name: idx_orders_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_status ON public.orders USING btree (status);


--
-- TOC entry 4752 (class 1259 OID 579369)
-- Name: idx_products_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_category ON public.products USING btree (category);


--
-- TOC entry 4753 (class 1259 OID 579368)
-- Name: idx_products_farmer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_farmer_id ON public.products USING btree (farmer_id);


--
-- TOC entry 4754 (class 1259 OID 579370)
-- Name: idx_products_is_available; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_is_available ON public.products USING btree (is_available);


--
-- TOC entry 4742 (class 1259 OID 579329)
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- TOC entry 4743 (class 1259 OID 579330)
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- TOC entry 4771 (class 2620 OID 579415)
-- Name: market_prices trg_market_prices_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_market_prices_updated_at BEFORE UPDATE ON public.market_prices FOR EACH ROW EXECUTE FUNCTION public.update_market_prices_updated_at();


--
-- TOC entry 4770 (class 2620 OID 579399)
-- Name: orders trg_orders_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON public.orders FOR EACH ROW EXECUTE FUNCTION public.update_orders_updated_at();


--
-- TOC entry 4766 (class 2606 OID 579343)
-- Name: crops crops_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- TOC entry 4768 (class 2606 OID 579385)
-- Name: orders orders_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- TOC entry 4769 (class 2606 OID 579390)
-- Name: orders orders_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT;


--
-- TOC entry 4767 (class 2606 OID 579363)
-- Name: products products_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(id) ON DELETE CASCADE;


-- Completed on 2026-08-01 21:06:23

--
-- PostgreSQL database dump complete
--

