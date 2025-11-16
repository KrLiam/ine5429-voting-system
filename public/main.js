
async function get_key() {
    let r = await fetch("/key");
    let json = await r.json();
    
    let n = BigInt(json.n)
    let g = BigInt(json.g)
    
    return {n, g}
}

async function get_candidates() {
    let r = await fetch("/candidates");
    let json = await r.json();

    return [...json]
}

async function get_end_time() {
    let r = await fetch("/endtime");
    let json = await r.json();

    return json.endtime;
}

async function validate_id(id) {
    let r = await fetch(`/validate-id?id=${encodeURIComponent(id)}`);
    let data = await r.json();

    return data.valid ?? false
}

async function send_vote(id, value) {
    let r = await fetch("/vote", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ id, value}),
    })
    return await r.json()
}

async function get_result() {
    let r = await fetch("/result");
    return await r.json();
}


function get_random_r() {
    let arr = new BigUint64Array(32);
    crypto.getRandomValues(arr);

    let r = BigInt(arr[0]);
    for (let i = 1; i < arr.length; i++) {
        r = (r << BigInt(64)) | BigInt(arr[i]);
    }

    return r
}


function powmod(x, n, M) {
    let res = 1n;

    while (n >= 1n) {
        if (n % 2n === 1n) {
            res = (res * x) % M;
            n -= 1n;
        }
        else {
            x = (x * x) % M;
            n /= 2n;
        }
    }

    return res;
}

function encrypt(value, key) {
    let n = key.n;
    let g = key.g;
    let n2 = n * n;

    let r = get_random_r();

    let c = ( powmod(g, value, n2) * powmod(r, n, n2) ) % n2;
    return c;
}


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
    createApp({
        data() {
            return {
                loading: true,
                candidates: [],
                key: {},
                end_time: 0,
                remaining_time: 0,
                result: null,

                id: null,
                input_id: "",
            };
        },
        async mounted() {
            let app = this;

            // carrega dados da api
            this.candidates = await get_candidates();
            this.key = await get_key();
            this.end_time = await get_end_time();
            await result_poller();

            this.loading = false;

            // atualizar timer
            function update_timer() {
                app.remaining_time = Math.max(0, app.end_time - Date.now() / 1000);
                setTimeout(update_timer, 100);
            }
            update_timer()

            // poller do resultado
            async function result_poller() {
                let r = await get_result();
                if (r.ok) {
                    app.result = r.result;
                    return;
                }
                setTimeout(result_poller, 1000);
            }
        },
        computed: {
            formatted_remaining_time() {
                
                return formatTime(this.remaining_time)
            },
        },
        methods: {
            async validateId() {
                let valid = await validate_id(this.input_id);
                if (valid) {
                    this.id = this.input_id;
                }
            },
            async vote(index) {
                let c = this.candidates.length;
                let vote = Array.from(new Array(c), () => BigInt(0));
                vote[index] = BigInt(1);

                console.log("Your vote is [" + vote.toString() + "]");

                for (let i = 0; i < vote.length; i++) {
                    vote[i] = encrypt(vote[i], this.key).toString(10);
                }

                console.log("Sending encrypted vote [", vote.toString(), "]");
                let response = await send_vote(this.id, vote);
                console.log(response.message);
            },
        }
    }).mount("#app");
}


const { createApp } = Vue;

main();


