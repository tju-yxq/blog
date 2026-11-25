const app = Vue.createApp({
    mixins: Object.values(mixins),
    data() {
        return {
            loading: true,
            hiddenMenu: false,
            showMenuItems: false,
            menuColor: false,
            scrollTop: 0,
            renderers: [],
        };
    },
    created() {
        window.addEventListener("load", () => {
            this.loading = false;
        });
    },
    mounted() {
        window.addEventListener("scroll", this.handleScroll, true);
        this.render();
        this.updateTocActive();
    },
    methods: {
        render() {
            for (let i of this.renderers) i();
        },
        updateTocActive() {
            let toc = document.getElementById("post-toc");
            if (!toc) return;
            let links = Array.from(toc.querySelectorAll("a.toc-link"));
            if (!links.length) return;
            let active = links[0];
            let scrollY = window.scrollY + 110;
            for (let link of links) {
                let hash = link.getAttribute("href");
                if (!hash || !hash.startsWith("#")) continue;
                let id = decodeURIComponent(hash.slice(1));
                let el = document.getElementById(id);
                if (el && el.getBoundingClientRect().top + window.scrollY <= scrollY) {
                    active = link;
                }
            }
            for (let link of links) {
                link.classList.toggle("active", link === active);
            }
        },
        handleScroll() {
            let wrap = this.$refs.homePostsWrap;
            let newScrollTop = document.documentElement.scrollTop;
            this.hiddenMenu = false;
            if (wrap) {
                if (newScrollTop <= window.innerHeight - 100) this.menuColor = true;
                else this.menuColor = false;
                if (newScrollTop <= 400) wrap.style.top = "-" + newScrollTop / 5 + "px";
                else wrap.style.top = "-80px";
            }
            this.scrollTop = newScrollTop;
            this.updateTocActive();
        },
    },
});
app.mount("#layout");
