import homeBrand from '../../assets/stickers/food/bakery_chiikawa_sign_001.png';
import brandMark from '../../assets/stickers/food/chiikawa_food_yellow_116.png';
import profileButton from '../../assets/stickers/food/hachiware_donut_badge_012.png';
import menuLogout from '../../assets/stickers/reaction/rest_text_pink_094.png';

import navOverview from '../../assets/stickers/work/hachiware_clipboard_blue_091.png';
import navSourcing from '../../assets/stickers/reaction/construction_yellow_053.png';
import navCatalog from '../../assets/stickers/cards/ticket_frame_pink_099.png';
import navCreative from '../../assets/stickers/cards/shutter_chance_card_037.png';
import navFlow from '../../assets/stickers/pennants/pennant_cat_pink_blue_071.png';
import navHome from '../../assets/stickers/food/acorn_character_brown_117.png';
import navToggleOpen from '../../assets/stickers/reaction/break_text_blue_093.png';
import navToggleClose from '../../assets/stickers/reaction/rest_text_pink_094.png';

import decorSidebarA from '../../assets/stickers/pennants/pennant_hachiware_blue_044.png';
import decorSidebarB from '../../assets/stickers/pennants/pennant_rabbit_yellow_043.png';

import metricImported from '../../assets/stickers/cards/collage_blue_109.png';
import metricListed from '../../assets/stickers/work/rabbit_apron_orange_111.png';
import metricPending from '../../assets/stickers/reaction/rest_text_pink_094.png';
import metricWorkflow from '../../assets/stickers/group/trio_basic_white_105.png';

import actionSearch from '../../assets/stickers/reaction/hachiware_speech_blue_061.png';
import actionAdd from '../../assets/stickers/food/chiikawa_food_yellow_116.png';
import actionFilter from '../../assets/stickers/work/rabbit_clipboard_yellow_090.png';
import actionFlow from '../../assets/stickers/pennants/pennant_cat_pink_blue_071.png';
import actionImport from '../../assets/stickers/group/trio_speech_yellow_106.png';
import actionView from '../../assets/stickers/cards/face_message_card_100.png';
import actionGenerate from '../../assets/stickers/reaction/black_camera_panel_011.png';
import actionImage from '../../assets/stickers/cards/pastel_doodle_panel_084.png';
import actionHistory from '../../assets/stickers/cards/vertical_tag_duo_038.png';
import actionStar from '../../assets/stickers/reaction/white_flower_cheer_017.png';
import actionSupplier from '../../assets/stickers/work/bear_officer_yellow_088.png';
import actionPrev from '../../assets/stickers/reaction/rabbit_white_speech_062.png';
import actionNext from '../../assets/stickers/reaction/mouse_orange_speech_114.png';
import actionLink from '../../assets/stickers/reaction/hamster_hello_pink_108.png';
import actionPause from '../../assets/stickers/reaction/rest_text_pink_094.png';
import actionRetry from '../../assets/stickers/reaction/break_text_blue_093.png';
import actionPlay from '../../assets/stickers/reaction/rabbit_smile_yellow_019.png';

import statusCompleted from '../../assets/stickers/food/hachiware_food_yellow_115.png';
import statusRunning from '../../assets/stickers/reaction/hachiware_speech_blue_061.png';
import statusPending from '../../assets/stickers/reaction/hachiware_speech_white_110.png';
import statusFailed from '../../assets/stickers/reaction/hachiware_scream_white_096.png';

import dashboardEcommerce from '../../assets/stickers/pennants/pennant_rabbit_yellow_043.png';
import dashboardStocks from '../../assets/stickers/pennants/pennant_hachiware_blue_044.png';
import dashboardNews from '../../assets/stickers/pennants/pennant_chiikawa_pink_045.png';
import dashboardAuth from '../../assets/stickers/pennants/pennant_momonga_purple_041.png';

export const stickers = {
  brand: {
    home: homeBrand,
    mark: brandMark,
    profile: profileButton,
    logout: menuLogout,
  },
  nav: {
    overview: navOverview,
    sourcing: navSourcing,
    catalog: navCatalog,
    creative: navCreative,
    flow: navFlow,
    home: navHome,
    toggleOpen: navToggleOpen,
    toggleClose: navToggleClose,
  },
  decor: {
    sidebarA: decorSidebarA,
    sidebarB: decorSidebarB,
  },
  metrics: {
    imported: metricImported,
    listed: metricListed,
    pending: metricPending,
    workflow: metricWorkflow,
  },
  actions: {
    search: actionSearch,
    add: actionAdd,
    filter: actionFilter,
    flow: actionFlow,
    import: actionImport,
    view: actionView,
    generate: actionGenerate,
    image: actionImage,
    history: actionHistory,
    star: actionStar,
    supplier: actionSupplier,
    prev: actionPrev,
    next: actionNext,
    link: actionLink,
    pause: actionPause,
    retry: actionRetry,
    play: actionPlay,
  },
  status: {
    completed: statusCompleted,
    running: statusRunning,
    pending: statusPending,
    failed: statusFailed,
  },
  dashboard: {
    ecommerce: dashboardEcommerce,
    stocks: dashboardStocks,
    news: dashboardNews,
    auth: dashboardAuth,
  },
} as const;
