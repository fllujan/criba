// Textos que dependen de datos del núcleo (errores, etapas) y formatos en español.
.pragma library

function error(kind) {
    switch (kind) {
    case "NOT_FOUND": return qsTr("No se ha encontrado el archivo.")
    case "PASSWORD_PROTECTED": return qsTr("Este PDF está protegido con contraseña.")
    case "CORRUPT": return qsTr("No se ha podido abrir este archivo.")
    case "TOO_MANY_PAGES": return qsTr("Este PDF tiene más de 1.500 páginas. Elige uno más corto o divídelo.")
    case "TOO_LARGE": return qsTr("Este PDF ocupa más de 500 MB. Elige uno más ligero.")
    case "NO_TEXT": return qsTr("No se ha encontrado texto en este PDF.")
    case "EXAM_TOO_LONG": return qsTr("Este examen tiene más de 50 páginas. Añade solo exámenes, no libros ni apuntes.")
    case "TOO_MANY_EXAMS": return qsTr("Añade como mucho 10 exámenes.")
    case "EXAMS_TOO_BIG": return qsTr("Entre todos, los exámenes pasan de 60 páginas o de 20 escaneadas. Quita alguno.")
    case "INVALID_KEY": return qsTr("La clave de API no es válida o ha caducado.")
    case "NO_CREDIT": return qsTr("Tu cuenta de Anthropic no tiene saldo suficiente.")
    case "OFFLINE": return qsTr("No hay conexión a Internet. Lo procesado se ha guardado.")
    case "RATE_LIMITED": return qsTr("El servicio está saturado. Se reintentará automáticamente.")
    case "DISK_FULL": return qsTr("No hay espacio para guardar el PDF.")
    case "CANNOT_WRITE": return qsTr("No se puede guardar en esa carpeta. Elige otra.")
    case "SERVICE_ERROR": return qsTr("El servicio de IA ha rechazado la petición. Lo procesado se ha guardado.")
    case "PROCESSING_FAILED": return qsTr("No se ha podido procesar el libro. Lo procesado se ha guardado.")
    case "RENDER_FAILED": return qsTr("No se han podido generar los PDF. Lo procesado se ha guardado.")
    case "NO_KEY": return qsTr("Falta la clave de API de Anthropic.")
    default: return qsTr("Algo no ha ido bien. Lo procesado se ha guardado.")
    }
}

function action(name) {
    switch (name) {
    case "elegir_otro_archivo": return qsTr("Elegir otro archivo")
    case "cambiar_clave": return qsTr("Cambiar clave")
    case "abrir_consola": return qsTr("Abrir la consola de Anthropic")
    case "reintentar": return qsTr("Reintentar")
    case "esperar": return qsTr("Esperar")
    case "cancelar": return qsTr("Cancelar")
    case "elegir_otra_carpeta": return qsTr("Elegir otra carpeta")
    default: return name
    }
}

function stage(name, chapter, chapters) {
    switch (name) {
    case "leyendo": return qsTr("Leyendo el libro")
    case "ocr": return qsTr("Leyendo las páginas escaneadas")
    case "analizando":
        return chapter > 0 && chapters > 0
            ? qsTr("Analizando el capítulo %1 de %2").arg(chapter).arg(chapters)
            : qsTr("Analizando el libro")
    case "sintetizando": return qsTr("Ordenando las ideas de cada capítulo")
    case "generando": return qsTr("Generando los dos PDF")
    case "listo": return qsTr("Listo")
    default: return qsTr("Preparando")
    }
}

// 1234.5 → "1.234,50"
function decimal(n, digits) {
    const fixed = Math.abs(n).toFixed(digits)
    const parts = fixed.split(".")
    const whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ".")
    return (n < 0 ? "-" : "") + whole + (parts.length > 1 ? "," + parts[1] : "")
}

function integer(n) {
    return decimal(Math.round(n), 0)
}

function euros(n) {
    return qsTr("%1 €").arg(decimal(n, 2))
}

function dollars(n) {
    return qsTr("%1 $").arg(decimal(n, 2))
}

function duration(seconds) {
    if (seconds < 0)
        return qsTr("calculando…")
    const minutes = Math.round(seconds / 60)
    if (minutes < 1)
        return qsTr("menos de un minuto")
    if (minutes === 1)
        return qsTr("un minuto")
    if (minutes < 90)
        return qsTr("unos %1 minutos").arg(minutes)
    const hours = Math.floor(minutes / 60)
    const rest = minutes % 60
    return rest >= 15 ? qsTr("unas %1 h y %2 min").arg(hours).arg(rest) : qsTr("unas %1 h").arg(hours)
}

function pages(first, last) {
    return first === last ? qsTr("p. %1").arg(first) : qsTr("pp. %1–%2").arg(first).arg(last)
}

function date(iso) {
    const d = new Date(iso)
    if (isNaN(d.getTime()))
        return ""
    const months = [qsTr("enero"), qsTr("febrero"), qsTr("marzo"), qsTr("abril"), qsTr("mayo"), qsTr("junio"),
                    qsTr("julio"), qsTr("agosto"), qsTr("septiembre"), qsTr("octubre"), qsTr("noviembre"), qsTr("diciembre")]
    return qsTr("%1 de %2 de %3").arg(d.getDate()).arg(months[d.getMonth()]).arg(d.getFullYear())
}

function language(code) {
    switch (code) {
    case "es": return qsTr("Español")
    case "en": return qsTr("Inglés")
    case "fr": return qsTr("Francés")
    case "pt": return qsTr("Portugués")
    case "it": return qsTr("Italiano")
    case "de": return qsTr("Alemán")
    case "ca": return qsTr("Catalán")
    default: return qsTr("El del libro (automático)")
    }
}

function model(id) {
    switch (id) {
    case "claude-sonnet-5-5": return qsTr("Claude Sonnet 5.5")
    case "claude-haiku-5-5": return qsTr("Claude Haiku 5.5")
    case "claude-opus-5-5": return qsTr("Claude Opus 5.5")
    default: return id
    }
}

function modelHint(id) {
    switch (id) {
    case "claude-sonnet-5-5": return qsTr("Equilibrio entre calidad y precio. Recomendado.")
    case "claude-haiku-5-5": return qsTr("El más barato y rápido; resúmenes algo más simples.")
    case "claude-opus-5-5": return qsTr("El más preciso; cuesta unas dos veces más.")
    default: return ""
    }
}

function pageCount(n) {
    return n === 1 ? qsTr("1 pág.") : qsTr("%1 págs.").arg(integer(n))
}

function exams(n) {
    return n === 1 ? qsTr("1 examen antiguo") : qsTr("%1 exámenes antiguos").arg(integer(n))
}

function books(n) {
    return n === 1 ? qsTr("1 libro") : qsTr("%1 libros").arg(integer(n))
}

// «18 oct 2026»: cabe en una línea del margen.
function shortDate(iso) {
    const d = new Date(iso)
    if (isNaN(d.getTime()))
        return ""
    const months = [qsTr("ene"), qsTr("feb"), qsTr("mar"), qsTr("abr"), qsTr("may"), qsTr("jun"),
                    qsTr("jul"), qsTr("ago"), qsTr("sep"), qsTr("oct"), qsTr("nov"), qsTr("dic")]
    return qsTr("%1 %2 %3").arg(d.getDate()).arg(months[d.getMonth()]).arg(d.getFullYear())
}

// Al comprobar la clave no hay nada «procesado» ni reintentos automáticos.
function keyError(kind) {
    switch (kind) {
    case "INVALID_KEY": return qsTr("La clave de API no es válida o ha caducado. Revisa que la has copiado entera.")
    case "NO_CREDIT": return qsTr("La clave es correcta, pero tu cuenta de Anthropic no tiene saldo. Añádelo en la consola y vuelve a probar.")
    case "OFFLINE": return qsTr("No hay conexión a Internet. Conéctate y vuelve a probar.")
    case "NO_KEY": return qsTr("No se ha podido guardar la clave en el llavero del sistema.")
    default: return qsTr("Anthropic no responde ahora mismo. Inténtalo de nuevo en unos minutos.")
    }
}
