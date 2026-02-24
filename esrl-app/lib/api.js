export function getApiBase() {
    const raw = process.env.NEXT_PUBLIC_API_URI || "http://127.0.0.1:5140"
    return raw.endsWith("/") ? raw.slice(0, -1) : raw
}

export function joinApiUrl(path) {
    const base = getApiBase()
    const normalizedPath = path.startsWith("/") ? path : `/${path}`
    return `${base}${normalizedPath}`
}
