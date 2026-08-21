// Склад ПРО — desktop-оболочка (Electron).
// Режимы:
//   локальный  — сам запускает склад-server.exe на 127.0.0.1:8700 (база на этом ПК);
//   сетевой    — открывает сервер по адресу, заданному в настройках (клиент в сети).
const { app, BrowserWindow, Menu, ipcMain } = require('electron')
const { spawn } = require('child_process')
const fs = require('fs')
const http = require('http')
const os = require('os')
const path = require('path')

const PORT = process.env.SKLAD_PORT || 8700
const LOCAL_URL = `http://127.0.0.1:${PORT}/`
const DATA_DIR = path.join(process.env.LOCALAPPDATA || os.homedir(), 'SkladPro', 'data')
const CONFIG_FILE = path.join(process.env.LOCALAPPDATA || os.homedir(), 'SkladPro', 'config.json')

// Раскладка ресурсов:
//   prod:  resources/sklad-server/sklad-server.exe, resources/web/dist
//   dev:   server/dist/sklad-server/sklad-server.exe, web/dist
const isDev = !app.isPackaged
const SERVER_EXE = isDev
  ? path.join(__dirname, '..', '..', 'server', 'dist', 'sklad-server', 'sklad-server.exe')
  : path.join(process.resourcesPath, 'sklad-server', 'sklad-server.exe')
const DIST_DIR = isDev
  ? path.join(__dirname, '..', '..', 'web', 'dist')
  : path.join(process.resourcesPath, 'web', 'dist')

let serverProc = null
let mainWindow = null
let settingsWindow = null
let currentUrl = LOCAL_URL

function readConfig() {
  try {
    const c = JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf8'))
    return c.serverUrl || null
  } catch {
    return null
  }
}

function writeConfig(url) {
  fs.mkdirSync(path.dirname(CONFIG_FILE), { recursive: true })
  fs.writeFileSync(CONFIG_FILE, JSON.stringify({ serverUrl: url }, null, 2))
}

function httpGet(url) {
  return new Promise((resolve, reject) => {
    const req = http.get(url, (res) => {
      res.resume()
      resolve(res.statusCode)
    })
    req.on('error', reject)
    req.setTimeout(2000, () => { req.destroy(new Error('timeout')) })
  })
}

// --- Сервер (локальный режим) -------------------------------------------------

function startServer() {
  if (!fs.existsSync(SERVER_EXE)) {
    // Dev-режим: собранный exe ещё нет — сервер должен уже работать (dev.bat).
    console.log('sklad-server.exe не найден, ожидаем уже запущенный сервер (' + SERVER_EXE + ')')
    return
  }
  const logFile = path.join(DATA_DIR, 'server.log')
  fs.mkdirSync(DATA_DIR, { recursive: true })
  const out = fs.openSync(logFile, 'a')
  serverProc = spawn(SERVER_EXE, [], {
    env: {
      ...process.env,
      SKLAD_DATA_DIR: DATA_DIR,
      SKLAD_DIST_DIR: DIST_DIR,
      SKLAD_PORT: String(PORT),
      SKLAD_HOST: '127.0.0.1', // локальный сервер — только для этого ПК
    },
    stdio: ['ignore', out, out],
    windowsHide: true,
  })
  serverProc.on('error', (err) => {
    console.error('Не удалось запустить sklad-server.exe:', err.message)
  })
  serverProc.on('exit', (code) => {
    console.log(`sklad-server.exe завершился (код ${code})`)
  })
}

async function waitForServer(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const code = await httpGet(LOCAL_URL + 'api/health')
      if (code === 200) return true
    } catch { /* ещё запускается */ }
    await new Promise((r) => setTimeout(r, 500))
  }
  return false
}

function stopServer() {
  if (serverProc && serverProc.exitCode === null) {
    try { serverProc.kill() } catch { /* уже не жив */ }
  }
  serverProc = null
}

// --- Окна ---------------------------------------------------------------------

function createWindow(url) {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 960,
    minHeight: 600,
    title: 'Склад ПРО',
    show: false,
    webPreferences: { contextIsolation: true },
  })
  const loading = 'data:text/html;charset=utf-8,' + encodeURIComponent(
    '<html><head><meta charset="utf-8"></head>' +
    '<body style="display:flex;height:100vh;align-items:center;justify-content:center;' +
    'font-family:Segoe UI,Arial,sans-serif;font-size:18px;color:#444">' +
    'Подключение к серверу…</body></html>'
  )
  mainWindow.loadURL(loading)
  mainWindow.once('ready-to-show', () => mainWindow.show())
  mainWindow.webContents.setWindowOpenHandler(({ url: u }) => {
    require('electron').shell.openExternal(u)
    return { action: 'deny' }
  })
  return mainWindow
}

function openMain(url) {
  currentUrl = url
  const win = createWindow(url)
  // Короткая задержка: локальный сервер должен ответить на /api/health.
  setTimeout(async () => {
    const ok = url === LOCAL_URL
      ? await waitForServer()
      : await httpGet(url + 'api/health').then((c) => c === 200).catch(() => false)
    if (!mainWindow || mainWindow.isDestroyed()) return
    if (ok) {
      mainWindow.loadURL(url)
    } else {
      const msg = url === LOCAL_URL
        ? 'Не удалось запустить встроенный сервер. Подробности: server.log в папке данных.'
        : 'Сервер по адресу ' + url + ' не отвечает. Проверьте адрес (настройки) и доступность.'
      mainWindow.loadURL('data:text/html;charset=utf-8,' + encodeURIComponent(
        `<html><head><meta charset="utf-8"></head>` +
        `<body style="display:flex;height:100vh;align-items:center;justify-content:center;padding:40px;` +
        `font-family:Segoe UI,Arial,sans-serif;font-size:16px;color:#a33;text-align:center">${msg}</body></html>`
      ))
    }
  }, 300)
  return win
}

function showSettings() {
  if (settingsWindow && !settingsWindow.isDestroyed()) {
    settingsWindow.focus()
    return
  }
  settingsWindow = new BrowserWindow({
    width: 480,
    height: 320,
    resizable: false,
    title: 'Настройки — Склад ПРО',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.cjs'),
    },
  })
  settingsWindow.setMenuBarVisibility(false)
  settingsWindow.loadFile('settings.html')
  settingsWindow.on('closed', () => {
    settingsWindow = null
    // Если основное окно ещё не открыто — настройки были окном первого запуска.
    if (!mainWindow || mainWindow.isDestroyed()) app.quit()
  })
}

// --- IPC из окна настроек ------------------------------------------------------

function openLocal() {
  startServer()
  return openMain(LOCAL_URL)
}

ipcMain.handle('settings:local', () => {
  writeConfig(null)
  if (settingsWindow && !settingsWindow.isDestroyed()) settingsWindow.close()
  if (!mainWindow || mainWindow.isDestroyed()) openLocal()
})

ipcMain.handle('settings:network', (_e, url) => {
  let u = String(url || '').trim()
  if (!/^https?:\/\//i.test(u)) u = 'http://' + u
  writeConfig(u)
  if (settingsWindow && !settingsWindow.isDestroyed()) settingsWindow.close()
  if (!mainWindow || mainWindow.isDestroyed()) openMain(u)
})

// --- Точка входа ----------------------------------------------------------------

app.whenReady().then(() => {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: 'Склад ПРО', submenu: [
      { label: 'Настройки (адрес сервера)', click: () => showSettings() },
      { type: 'separator' },
      { role: 'quit', label: 'Выход' },
    ] },
  ]))

  const serverUrl = readConfig()

  if (process.argv.includes('--smoke')) {
    // Автотест сборки: открыть главное окно и выйти после загрузки.
    console.log('SMOKE start, mode=' + (serverUrl ? 'network' : 'local'))
    const win = serverUrl ? openMain(serverUrl) : openLocal()
    let done = false
    const finish = (code, msg) => {
      if (done) return
      done = true
      console.log(`SMOKE_EXIT ${code} ${msg}`)
      app.exit(code)
    }
    setTimeout(() => finish(2, 'timeout: страница не загрузилась за 90 с'), 90000)
    win.webContents.on('did-finish-load', () => {
      const u = win.webContents.getURL()
      if (u.startsWith('data:')) {
        console.log('SMOKE page: ' + u.slice(0, 60) + '...')
        return
      }
      const title = win.webContents.getTitle()
      console.log('SMOKE loaded url=' + u + ' title=' + title)
      finish(title ? 0 : 1, 'title=' + title)
    })
    win.webContents.on('console-message', (_e, _lvl, message) => {
      console.log('SMOKE [renderer] ' + message)
    })
    return
  }

  if (serverUrl) {
    openMain(serverUrl)
  } else if (fs.existsSync(SERVER_EXE)) {
    // Первый запуск (или сброс настроек): выбрать режим работы.
    showSettings()
  } else {
    // Dev-режим без собранного exe: открываем уже работающий dev-сервер.
    openMain(LOCAL_URL)
  }
})

app.on('before-quit', () => stopServer())
app.on('window-all-closed', () => {
  stopServer()
  app.quit()
})
