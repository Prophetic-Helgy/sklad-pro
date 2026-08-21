// Предзагрузка для окна настроек: мост между страницей и main-процессом.
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('sklad', {
  chooseLocal: () => ipcRenderer.invoke('settings:local'),
  chooseNetwork: (url) => ipcRenderer.invoke('settings:network', url),
})
