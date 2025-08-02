"
" Make sure https://github.com/junegunn/vim-plug is installed
"

set nocompatible              " be iMproved, required
filetype off                  " required

nnoremap <S-W> :q<CR>
nnoremap <S-X> :qa<CR>
nnoremap <S-S> :w<CR>
nnoremap <C-K><C-D> ggvG= " like visual studio

set number relativenumber
set ruler
set wildmenu
set cmdheight=2

" leader key
let mapleader='`'

" CTAGS
set tags=tags;

"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
" => Colors and Fonts
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
set background=dark

" Set extra options when running in GUI mode
if has("gui_running")
    set guioptions-=T
    set guioptions-=e
    set t_Co=256
    set guitablabel=%M\ %t
endif

" Set utf8 as standard encoding and en_US as the standard language
set encoding=utf8

" Use Unix as the standard file type
set ffs=unix,dos,mac

if has("gui_running")
  if has("gui_gtk2")
    set guifont=Inconsolata\ 12
  elseif has("gui_macvim")
    set guifont=Menlo\ Regular:h14
  elseif has("gui_win32")
    set guifont=Consolas:h11:cANSI
  endif
endif

set mouse=a                 " Automatically enable mouse usage
set mousehide               " Hide the mouse cursor while typing
set cursorline                  " Highlight current line
set guicursor+=a:blinkon0

set hlsearch

"""""""""""""""""""""""""""""""""
" Tabs And Spaces
"""""""""""""""""""""""""""""""""
set expandtab
set smarttab

" 1 tab == 4 spaces
set shiftwidth=4
set tabstop=4
set softtabstop=4
set nojoinspaces
set splitright
set splitbelow
set linespace=0
set showmatch
set ignorecase

autocmd BufEnter * if expand("%:p:h") !~ '^/tmp' | silent! lcd %:p:h | endif

""""""""""""""""""""""""""""""""
" Packages managed by VIM-Plug
""""""""""""""""""""""""""""""""

call plug#begin('~/.vim/plugged')

Plug 'scrooloose/nerdtree'
Plug 'majutsushi/tagbar'
" Required for git branch to be displayed on airline
Plug 'tpope/vim-fugitive'
Plug 'vim-airline/vim-airline'
Plug 'vim-airline/vim-airline-themes'
Plug 'easymotion/vim-easymotion'
Plug 'ddollar/nerdcommenter'
Plug 'tpope/vim-repeat'
Plug 'terryma/vim-multiple-cursors'
Plug 'mileszs/ack.vim'
Plug 'altercation/vim-colors-solarized'
Plug 'nathanaelkane/vim-indent-guides'
Plug 'mbbill/undotree'
Plug 'kien/ctrlp.vim'
Plug 'Xuyuanp/nerdtree-git-plugin'
Plug 'scrooloose/syntastic'
Plug 'luochen1990/rainbow'
Plug 'godlygeek/tabular'
Plug 'valloric/youcompleteme'
Plug 'greyblake/vim-preview'
Plug 'shougo/unite.vim'
Plug 'tungd/unite-session'
Plug 't9md/vim-unite-lines'
Plug 'ludovicchabant/vim-gutentags'
Plug 'Yggdroot/LeaderF', { 'do': '.\install.bat' }
Plug 'mihais/vim-mark'

call plug#end()

" call :PlugInstall to install

""""""""""""""""""""""""""""""
" NERDTREE
""""""""""""""""""""""""""""""
" auto open NERDTree when vim starts up.
" Disable this because SessionIssue
" autocmd VimEnter * NERDTree

" change the cursor focus to the file
" autocmd VimEnter * wincmd p

" auto close NERDTree when treeview is the last window.
autocmd bufenter * if (winnr("$") == 1 && exists("b:NERDTree") && b:NERDTree.isTabTree()) | q | endif

" autocmd VimEnter * NERDTreeTabs

nnoremap <F6> :NERDTree<CR>

let g:NERDTreeWinSize = 30 
let g:NERDTreeIgnore = ['\.dll$', '\.exe$', '\.obj$', '\.lib$', '\.pdb$', '\.out$', '\.a$', '\.o$']

let NERDTreeShowBookmarks=1
let NERDTreeKeepTreeInNewTab=1
let g:nerdtree_tabs_open_on_gui_startup=0

""""""""""""""""""""""""""""""
" TAGBAR
""""""""""""""""""""""""""""""
nmap <F8> :TagbarToggle<CR>

""""""""""""""""""""""""""""""
" VIM-AIRLINE
""""""""""""""""""""""""""""""
" enable the tabline
let g:airline#extensions#tabline#enabled = 1
let g:airline#extensions#tabline#left_sep = ' '
let g:airline#extensions#tabline#left_alt_sep = '|'
let g:airline#extensions#tabline#buffer_nr_show = 1

let g:airline_left_sep='›'  " Slightly fancier than '>'
let g:airline_right_sep='‹' " Slightly fancier than '<'


if has('win32') 
    set encoding=utf-8   
endif

nnoremap <S-Left> :bp<CR>
nnoremap <S-Right> :bn<CR>
nnoremap <S-Q> :bd<CR>

" Switch window mappings
" nnoremap <C-L> <C-W><C-L>

if has('nvim')
    nnoremap <BS> <C-W>h
endif

:nnoremap <silent> <C-h> :wincmd h<CR>
:nnoremap <silent> <C-j> :wincmd j<CR>
:nnoremap <silent> <C-k> :wincmd k<CR>
:nnoremap <silent> <C-l> :wincmd l<CR>

if has('statusline')
    set laststatus=2
endif

""""""""""""""""""""""""""""""
" easy motion
""""""""""""""""""""""""""""""
let g:easymotion_smartcase = 1

" /<keyword> <enter> shows the keyword motion key
map  / <plug>(easymotion-sn)

" \l shows the line motion key
nmap <leader>l <plug>(easymotion-overwin-line)
map <leader>l <plug>(easymotion-bd-jk)

" \w shows the word motion key
map  <leader>w <plug>(easymotion-bd-w)
nmap <leader>w <plug>(easymotion-overwin-w)

""""""""""""""""""""""""""""""
" nerdcommenter
""""""""""""""""""""""""""""""
" let g:nerdspacedelims=1

""""""""""""""""""""""""""""""
" repeat
""""""""""""""""""""""""""""""
silent! call repeat#set("\<plug>mywonderfulmap", v:count)

""""""""""""""""""""""""""""""
" solarized - must put after vundle
""""""""""""""""""""""""""""""
syntax enable

if has('gui_running')
    set background=dark
else
    set background=dark

    " use degraded 256 colors in ternimal mode
    let g:solarized_termcolors=256
endif

let g:solarized_italic=0
colorscheme solarized

""""""""""""""""""""""""""""""
" undo tree
""""""""""""""""""""""""""""""
nnoremap <f9> :undotreetoggle<cr>

if has("persistent_undo")
    set undodir=~/.undodir/
    set undofile
endif

""""""""""""""""""""""""""""""
" rainbown
""""""""""""""""""""""""""""""
let g:rainbow_active = 1 "0 if you want to enable it later via :rainbowtoggle

""""""""""""""""""""""""""""""
" unit.vim
""""""""""""""""""""""""""""""
nnoremap <leader>us :Unite session<cr>
nnoremap <leader>ul :Unite lines<cr>
nnoremap <leader>ub :Unite buffer<cr>
nnoremap <leader>ur :Unite file<cr>

""""""""""""""""""""""""""""""
" ctrlp
""""""""""""""""""""""""""""""

let g:ctrlp_working_path_mode='ra'

let g:ctrlp_map = '<c-p>'
let g:ctrlp_cmd = 'CtrlP'
let g:ctrlp_lazy_update = 0
let g:ctrlp_clear_cache_on_exit = 0
let g:ctrlp_max_height = 20
let g:ctrlp_max_files=0
" let g:ctrlp_use_caching = 5000
let g:ctrlp_match_window_reversed = 1

if exists("g:ctrlp_user_command")
    unlet g:ctrlp_user_command
endif

if has('win32')
    let g:ctrlp_cache_dir = '$USERPROFILE/.vim/tmp/ctrlp'

    let g:ctrlp_custom_ignore = {
                \ 'dir':  '\v[\\](\.(git|hg|svn)|(obj|objd|out))$', 
                \ 'file': '\v\.(exe|so|dll|err|log|trc|wrn|prf|pyc|pdb|nupkg|sln)$',
                \ 'link': '',
                \ }
else
    let g:ctrlp_cache_dir = '~/.vim/tmp/ctrlp'

    let g:ctrlp_custom_ignore = {
                \ 'dir':  '\v[\/]\.(git|hg|svn)$',
                \ 'file': '\v\.(exe|so|dll|err|log|trc|wrn|prf|pyc|pdb|nupkg)$',
                \ 'link': '',
                \ }
endif

set wildignore+=*/tmp/*,*.so,*.swp,*.zip     " MacOSX/Linux
set wildignore+=*.swp,*.zip,*.exe,*.dll,*.pdb,*.nupkg,*\\obj\\*,*\\objd\\*,*\\tmp\\* " Windows

""""""""""""""""""""""""""""""
" leaderF (replace ctrlp)
""""""""""""""""""""""""""""""
nmap <Leader>ff :LeaderfFile<cr>
nmap <Leader>ft :LeaderfTag<cr>
nmap <Leader>fb :LeaderfBuffer<cr>
nmap <Leader>fm :LeaderfFunction<cr>

" current folder with git root
let g:Lf_WorkingDirectoryMode = 'Ac'  

" Notes:
"<C-C> : quit from LeaderF. 
"<C-R> : switch between fuzzy search mode and regex mode. 
"<C-F> : switch between full path search mode and name only search mode. 

""""""""""""""""""""""""""""""
" sessionmanager
""""""""""""""""""""""""""""""
nmap <leader>sl :sessionlist<cr>
nmap <leader>ss :sessionsave<cr>
nmap <leader>sc :SessionClose<CR>

""""""""""""""""""""""""""""""
" YouCompleteMe
""""""""""""""""""""""""""""""
" disable when not launching from gui
if has("gui_running")
    let g:loaded_youcompleteme = 1
else
    let g:loaded_youcompleteme = 0
endif

"let g:ycm_add_preview_to_completeopt = 0
"let g:ycm_show_diagnostics_ui = 0
"let g:ycm_server_log_level = 'info'
"let g:ycm_min_num_identifier_candidate_chars = 2
"let g:ycm_collect_identifiers_from_comments_and_strings = 1
"let g:ycm_complete_in_strings=1
"let g:ycm_key_invoke_completion = '<c-z>'
"set completeopt=menu,menuone

"let g:ycm_semantic_triggers = {
"            \ 'c,cpp,python,java,go,erlang,perl': ['re!\w{2}'],
"            \ 'cs,lua,javascript': ['re!\w{2}'],
"            \ }

""""""""""""""""""""""""""""""
" Ack
""""""""""""""""""""""""""""""
cnoreabbrev Ack Ack!
cnoreabbrev ack Ack!
nnoremap <Leader>a :Ack! --ignore-case<Space>

if executable('ag')
    let g:ackprg = 'ag --vimgrep --ignore-case --nogroup'
else
    if has ('win32')
        let g:ackprg = 'silver_search --vimgrep --ignore-case --nogroup'
    else
        :echo "AG is NOT installed. It's strongly recommend to install that!"
    endif    
endif

""""""""""""""""""""""""""""""
" Gutentags
""""""""""""""""""""""""""""""
let g:gutentags_enabled = 0

""""""""""""""""""""""""""""""
" Highlight
""""""""""""""""""""""""""""""