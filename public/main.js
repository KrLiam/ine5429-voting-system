
////
// API

async function get_election() {
    let r = await fetch("/election");
    let data = await r.json();

    return {
        key: { n: BigInt(data.key.n), g: BigInt(data.key.g) },
        end_time: data.end_time,
        about: data.about,
        candidates: data.candidates,
    }
}

async function validate_token(token) {
    let r = await fetch(`/validate-token?token=${encodeURIComponent(token)}`);
    let data = await r.json();

    return data.valid ?? false
}

async function send_vote(token, value) {
    let r = await fetch("/vote", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ token, value}),
    })
    return await r.json()
}

async function get_result() {
    let r = await fetch("/result");
    let data = await r.json();
    return {
        ok: data.ok,
        result: data.result,
    }
}


////
// Cifragem

/**
 * Gera um inteiro pseudo-aleatório.
 */
function get_random_r() {
    // Gera um array de 32 inteiros de 64 bits
    let arr = new BigUint64Array(32);
    crypto.getRandomValues(arr);

    // Une-se os 32 inteiros para produzir um único inteiro de 2048 bits
    let r = BigInt(arr[0]);
    for (let i = 1; i < arr.length; i++) {
        r = (r << BigInt(64)) | BigInt(arr[i]);
    }

    return r
}

/**
 * Computa x^n mod m
 * @param {BigInt} x 
 * @param {BigInt} n 
 * @param {BigInt} m
 */
function powmod(x, n, m) {
    let res = 1n;

    while (n >= 1n) {
        if (n % 2n === 1n) {
            res = (res * x) % m;
            n -= 1n;
        }
        else {
            x = (x * x) % m;
            n /= 2n;
        }
    }

    return res;
}

/**
 * Cifra um valor utilizando a chave fornecida com o
 * esquema de Paillier.
 * 
 * @param {BigInt} value 
 * @param {{n: BigInt, g: BigInt}} key 
 */
function encrypt(value, key) {
    let n = key.n;
    let g = key.g;
    let n2 = n * n;

    let r = get_random_r();

    // função de cifragem de Paillier
    let c = ( powmod(g, value, n2) * powmod(r, n, n2) ) % n2;

    return c;
}


////
// Lógica da interface

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);

    return [
        h.toString().padStart(2, '0'),
        m.toString().padStart(2, '0'),
        s.toString().padStart(2, '0')
    ].join(':');
}


async function main() {
    const { createApp } = Vue;

    createApp({
        data() {
            return {
                loading: true,
                key: {},
                end_time: 0,
                about: "",
                candidates: [],

                remaining_time: 0,
                result: null,

                message: null,
                message_token_validation: null,

                token: null,
                input_token: "",
            };
        },
        async mounted() {
            let app = this;

            // carrega dados da api
            let [data, result] = await Promise.all([get_election(), get_result()]);
            this.candidates = data.candidates;
            this.key = data.key;
            this.end_time = data.end_time;
            this.about = data.about;
            if (result.ok) {
                this.result = result.result;
            }

            this.loading = false;

            // poller que executa a cada 0.1 segundos para atualizar o temporizador
            // e pedir resultado final quando o temporizador chegar a 0
            async function update_timer() {
                app.remaining_time = Math.max(0, app.end_time - Date.now() / 1000);

                if (app.remaining_time <= 0) {
                    let r = await get_result();
                    if (r.ok) {
                        app.result = r.result;
                        return;
                    }
                }

                setTimeout(update_timer, 100);
            }

            if (this.result === null) {
                update_timer()
            }
        },
        computed: {
            formatted_remaining_time() {
                return formatTime(this.remaining_time)
            },
            sorted_candidates() {
                if (this.result === null) return []

                // ordena os candidatos de acordo com o número de votos
                return this.result
                    .map((count, index) => ({ candidate: this.candidates[index], count }))
                    .sort((a,b) => b.count - a.count)
            }
        },
        methods: {
            async validate_token() {
                this.message_token_validation = null;
                // envia pedido de validação ao servidor
                let valid = await validate_token(this.input_token);

                if (valid) {
                    this.token = this.input_token;
                }
                else {
                    this.message_token_validation = "Token inválido."
                }
            },
            async vote(index) {
                // gera vetor do voto
                let c = this.candidates.length;
                let vote = Array.from(new Array(c), () => BigInt(0));
                vote[index] = BigInt(1);

                // cifra voto
                for (let i = 0; i < vote.length; i++) {
                    vote[i] = encrypt(vote[i], this.key).toString(10);
                }

                // envia o voto ao servidor
                let response = await send_vote(this.token, vote);
                this.message = response.message;
            },
        }
    }).mount("#app");
}

main();


