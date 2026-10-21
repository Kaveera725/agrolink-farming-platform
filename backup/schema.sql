--
-- PostgreSQL database dump
--

\restrict 6rz4MdRgKEXed8QGjGCD6au2S0ikrhozCkpkzliCqz1i8ZWNnc6Vx6eadz1aqTa

-- Dumped from database version 18.1
-- Dumped by pg_dump version 18.1

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: crop_status; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.crop_status AS ENUM (
    'growing',
    'ready',
    'harvested'
);


ALTER TYPE public.crop_status OWNER TO postgres;

--
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
-- Name: user_role; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.user_role AS ENUM (
    'farmer',
    'buyer'
);


ALTER TYPE public.user_role OWNER TO postgres;

--
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
-- Name: TABLE crops; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.crops IS 'Private crop tracking records for farmers.';


--
-- Name: COLUMN crops.farmer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.farmer_id IS 'FK → users.id. Only farmers own crop records.';


--
-- Name: COLUMN crops.quantity_kg; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.quantity_kg IS 'Expected yield in kilograms.';


--
-- Name: COLUMN crops.expected_harvest_date; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.expected_harvest_date IS 'Planned harvest date for planning purposes.';


--
-- Name: COLUMN crops.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.crops.status IS 'growing → ready → harvested lifecycle.';


--
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
-- Name: crops_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.crops_id_seq OWNED BY public.crops.id;


--
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
-- Name: TABLE market_prices; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.market_prices IS 'Reference market prices for Sri Lankan agricultural products.';


--
-- Name: COLUMN market_prices.buying_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_prices.buying_price IS 'Price farmers receive (LKR per kg).';


--
-- Name: COLUMN market_prices.selling_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.market_prices.selling_price IS 'Price buyers pay in the open market (LKR per kg).';


--
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
-- Name: market_prices_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.market_prices_id_seq OWNED BY public.market_prices.id;


--
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
-- Name: TABLE orders; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.orders IS 'Purchase orders placed by buyers for marketplace products.';


--
-- Name: COLUMN orders.buyer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.buyer_id IS 'FK → users.id. The buyer who placed the order.';


--
-- Name: COLUMN orders.product_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.product_id IS 'FK → products.id. The product being ordered.';


--
-- Name: COLUMN orders.total_price; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.total_price IS 'Snapshot of quantity_kg × price_per_kg at order time.';


--
-- Name: COLUMN orders.status; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.status IS 'pending → confirmed → delivered, or cancelled.';


--
-- Name: COLUMN orders.updated_at; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.orders.updated_at IS 'Auto-updated by trigger on every status change.';


--
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
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
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
-- Name: TABLE products; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.products IS 'Public product listings on the marketplace.';


--
-- Name: COLUMN products.farmer_id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.farmer_id IS 'FK → users.id. The farmer who listed this product.';


--
-- Name: COLUMN products.quantity_kg; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.quantity_kg IS 'Remaining stock. Decremented when orders are placed.';


--
-- Name: COLUMN products.is_available; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.products.is_available IS 'FALSE hides the listing without deleting it.';


--
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
-- Name: products_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.products_id_seq OWNED BY public.products.id;


--
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
-- Name: TABLE users; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON TABLE public.users IS 'All registered users — farmers and buyers.';


--
-- Name: COLUMN users.id; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.id IS 'Auto-incrementing primary key.';


--
-- Name: COLUMN users.email; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.email IS 'Unique login email address.';


--
-- Name: COLUMN users.password_hash; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.password_hash IS 'Werkzeug pbkdf2 password hash — never store plain text.';


--
-- Name: COLUMN users.role; Type: COMMENT; Schema: public; Owner: postgres
--

COMMENT ON COLUMN public.users.role IS 'farmer = can list products & manage crops; buyer = can place orders.';


--
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
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: crops id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops ALTER COLUMN id SET DEFAULT nextval('public.crops_id_seq'::regclass);


--
-- Name: market_prices id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_prices ALTER COLUMN id SET DEFAULT nextval('public.market_prices_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: products id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products ALTER COLUMN id SET DEFAULT nextval('public.products_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Name: crops crops_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_pkey PRIMARY KEY (id);


--
-- Name: market_prices market_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.market_prices
    ADD CONSTRAINT market_prices_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_crops_farmer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crops_farmer_id ON public.crops USING btree (farmer_id);


--
-- Name: idx_crops_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_crops_status ON public.crops USING btree (status);


--
-- Name: idx_market_prices_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_prices_category ON public.market_prices USING btree (category);


--
-- Name: idx_market_prices_crop; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_market_prices_crop ON public.market_prices USING btree (crop_name);


--
-- Name: idx_orders_buyer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_buyer_id ON public.orders USING btree (buyer_id);


--
-- Name: idx_orders_product_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_product_id ON public.orders USING btree (product_id);


--
-- Name: idx_orders_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_status ON public.orders USING btree (status);


--
-- Name: idx_products_category; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_category ON public.products USING btree (category);


--
-- Name: idx_products_farmer_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_farmer_id ON public.products USING btree (farmer_id);


--
-- Name: idx_products_is_available; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_products_is_available ON public.products USING btree (is_available);


--
-- Name: idx_users_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_email ON public.users USING btree (email);


--
-- Name: idx_users_role; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_users_role ON public.users USING btree (role);


--
-- Name: market_prices trg_market_prices_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_market_prices_updated_at BEFORE UPDATE ON public.market_prices FOR EACH ROW EXECUTE FUNCTION public.update_market_prices_updated_at();


--
-- Name: orders trg_orders_updated_at; Type: TRIGGER; Schema: public; Owner: postgres
--

CREATE TRIGGER trg_orders_updated_at BEFORE UPDATE ON public.orders FOR EACH ROW EXECUTE FUNCTION public.update_orders_updated_at();


--
-- Name: crops crops_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.crops
    ADD CONSTRAINT crops_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: orders orders_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.users(id) ON DELETE RESTRICT;


--
-- Name: orders orders_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.products(id) ON DELETE RESTRICT;


--
-- Name: products products_farmer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_farmer_id_fkey FOREIGN KEY (farmer_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- Name: TABLE crops; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.crops TO agrolink_db_user;


--
-- Name: SEQUENCE crops_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.crops_id_seq TO agrolink_db_user;


--
-- Name: TABLE market_prices; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.market_prices TO agrolink_db_user;


--
-- Name: SEQUENCE market_prices_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.market_prices_id_seq TO agrolink_db_user;


--
-- Name: TABLE orders; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.orders TO agrolink_db_user;


--
-- Name: SEQUENCE orders_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.orders_id_seq TO agrolink_db_user;


--
-- Name: TABLE products; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.products TO agrolink_db_user;


--
-- Name: SEQUENCE products_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.products_id_seq TO agrolink_db_user;


--
-- Name: TABLE users; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON TABLE public.users TO agrolink_db_user;


--
-- Name: SEQUENCE users_id_seq; Type: ACL; Schema: public; Owner: postgres
--

GRANT ALL ON SEQUENCE public.users_id_seq TO agrolink_db_user;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO agrolink_db_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO agrolink_db_user;


--
-- PostgreSQL database dump complete
--

\unrestrict 6rz4MdRgKEXed8QGjGCD6au2S0ikrhozCkpkzliCqz1i8ZWNnc6Vx6eadz1aqTa

